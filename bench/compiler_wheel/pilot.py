"""Verify and measure installed native/hosted compiler dispatch, locally only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
WORKLOADS = [
    ("self-ir", "ir", "pystachy.py"),
    ("json-ir", "ir", "bench/json_repair/codec.py"),
    ("bpe-ir", "ir", "bench/pyperformance/bpe_tokeniser.py"),
    ("json-aot-build", "build", "bench/json_repair/codec.py"),
]
PROGRAM = '''# pystachy: dynamic-any
import json
from typing import Any
value: Any = json.loads('{"snow":true,"values":[1,2,null]}')
print(json.dumps(value, sort_keys=True))
print(sum(i * i for i in range(10)))
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


class Pilot:
    def __init__(self, args):
        self.args = args
        self.out = args.output.resolve()
        self.out.mkdir(parents=True, exist_ok=True)
        self.work = self.out / "outside-checkout"
        self.work.mkdir(exist_ok=True)
        self.logs = self.out / "logs"
        self.logs.mkdir(exist_ok=True)
        self.report = self.out / "pilot.json"
        self.data = json.loads(self.report.read_text()) if self.report.exists() else {"runs": [], "checks": {}}
        self.environment = {k: v for k, v in os.environ.items()
                            if not k.startswith("PYSTACHY_") and k not in ("PYTHONHOME", "PYTHONPATH")}
        self.environment["PYSTACHY_LLVM"] = str(args.llvm.resolve())
        self.cli = args.native_cli.resolve()
        self.python = self.cli.parent / "python"
        path = subprocess.check_output(
            [str(self.python), "-I", "-c", "import _pystachy_source.pystachy_cli as c; print(c.__file__)"],
            cwd=self.work, text=True, env=self.environment,
        ).strip()
        self.package = Path(path).parent
        identity = self.current_identity()
        if "identity" in self.data and self.data["identity"] != identity:
            raise RuntimeError("installed compiler or workload identity changed")
        self.data["identity"] = identity
        self.flush()

    def current_identity(self):
        return {"time_sha256": digest(self.args.time_command),
                "native_binary_sha256": digest(self.package / "native/pystachy"),
                    "launcher_sha256": digest(self.package / "pystachy_cli.py"),
                    "native_receipt_sha256": digest(self.package / "native/manifest.json"),
                    "python": subprocess.check_output([str(self.python), "--version"], text=True).strip(),
                    "self_compiler_sources": {p.relative_to(ROOT).as_posix(): digest(p)
                                              for p in sorted((ROOT / "src").rglob("*.py"))},
                    "inputs": {name: digest(ROOT / relative) for name, _, relative in WORKLOADS},
                    "resources": {p.relative_to(self.package).as_posix(): digest(p)
                                  for p in sorted(self.package.rglob("*")) if p.is_file()
                                  and "__pycache__" not in p.parts and p.suffix != ".pyc"}}

    def flush(self):
        save(self.report, self.data)

    def run(self, name, command, backend="native", *, expected=0, pin=False):
        env = self.environment | {"PYSTACHY_COMPILER": backend,
                                   "PYSTACHY_CACHE": str(self.out / ("cache-" + backend))}
        cmd = (["taskset", "-c", str(self.args.cpu)] if pin else []) + [str(x) for x in command]
        number = len(self.data["runs"])
        stdout, stderr = (self.logs / f"{number:03d}-{name}.{suffix}" for suffix in ("out", "err"))
        rss = self.logs / f"{number:03d}-{name}.rss"
        cmd = [str(self.args.time_command), "-q", "-f", "%M", "-o", str(rss), *cmd]
        start = time.monotonic()
        with stdout.open("wb") as output, stderr.open("wb") as error:
            child = subprocess.Popen(cmd, cwd=self.work, env=env, stdout=output, stderr=error,
                                     start_new_session=True)
            timer = threading.Timer(300, lambda: os.killpg(child.pid, signal.SIGKILL))
            timer.daemon = True
            timer.start()
            try:
                _, status, usage = os.wait4(child.pid, 0)
                child.returncode = os.waitstatus_to_exitcode(status)
            finally:
                timer.cancel()
        row = {"name": name, "command": cmd, "backend": backend, "seconds": time.monotonic() - start,
               "returncode": child.returncode, "peak_rss_kib": int(rss.read_text().strip()),
               "outer_wait4_peak_rss_kib": usage.ru_maxrss,
               "user_seconds": usage.ru_utime, "system_seconds": usage.ru_stime,
               "stdout": str(stdout), "stderr": str(stderr)}
        self.data["runs"].append(row)
        self.flush()
        if child.returncode != expected or (expected == 0 and stderr.read_bytes()):
            raise RuntimeError(f"{name} failed; inspect {stderr}")
        return row, stdout.read_bytes()

    def equal(self, name, left, right):
        self.data["checks"][name] = left == right
        self.flush()
        if left != right:
            raise RuntimeError("output differs: " + name)

    def smoke(self):
        program = self.work / "smoke.py"
        program.write_text(PROGRAM)
        _, oracle = self.run("cpython-oracle", [self.python, program])
        for backend in ("hosted", "native"):
            _, got = self.run("jit-" + backend, [self.cli, "run", program], backend)
            self.equal("jit-" + backend, got, oracle)
            binary = self.work / ("smoke-" + backend)
            self.run("build-" + backend, [self.cli, "build", program, "-o", binary], backend)
            _, got = self.run("aot-" + backend, [binary], backend)
            self.equal("aot-" + backend, got, oracle)
        self.run("source-wheel-default", [self.args.source_cli, "check", program], "auto")
        self.run("source-wheel-forced-native", [self.args.source_cli, "check", program], "native", expected=1)
        self.data["checks"]["source-wheel-hosted-fallback"] = True
        # Remove the installed compiler Python implementation during the native
        # check. Output parity alone would not prove the native path was used.
        hidden = []
        try:
            for name in ("pystachy.py", "src"):
                path = self.package / name
                backup = self.package / (name + ".pilot-hidden")
                if backup.exists():
                    raise RuntimeError("unexpected existing temporary source backup")
                path.rename(backup)
                hidden.append((path, backup))
            self.run("native-without-python-compiler", [self.cli, "ir", program, "-o", self.work / "native-only.ll"], "auto")
            self.run("hosted-negative-control", [self.cli, "check", program], "hosted", expected=2)
            self.data["checks"]["native-path-proven-without-python-compiler"] = True
        finally:
            for path, backup in reversed(hidden):
                backup.rename(path)
        self.flush()

    def verify(self):
        for name, mode, relative in WORKLOADS:
            if mode != "ir":
                continue
            paths = []
            for backend in ("hosted", "native"):
                output = self.out / (name + "-" + backend + ".ll")
                self.run(name + "-verify-" + backend, [self.cli, mode, ROOT / relative, "-o", output], backend)
                paths.append(output)
            self.equal(name + "-exact-ir", paths[0].read_bytes(), paths[1].read_bytes())
        source = ROOT / "bench/json_repair/codec.py"
        _, oracle = self.run("json-codec-cpython", [self.python, source, "loads", "4", "2", "1", "0"])
        for backend in ("hosted", "native"):
            output = self.work / ("json-" + backend)
            self.run("json-aot-verify-" + backend, [self.cli, "build", source, "-o", output], backend)
            _, got = self.run("json-aot-run-" + backend, [output, "loads", "4", "2", "1", "0"], backend)
            # The workload already checks complete JSON equality; its printed
            # elapsed-time line is deliberately excluded from the output oracle.
            def meaningful(raw):
                return b"\n".join(line for line in raw.splitlines() if not line.startswith(b"seconds "))
            self.equal("json-aot-execution-" + backend, meaningful(got), meaningful(oracle))
        if self.current_identity() != self.data["identity"]:
            raise RuntimeError("inputs changed during verification")
        self.data["verified_identity"] = self.data["identity"]
        self.flush()

    def measure(self):
        required = [name + "-exact-ir" for name, mode, _ in WORKLOADS if mode == "ir"]
        required += ["json-aot-execution-hosted", "json-aot-execution-native",
                     "jit-hosted", "jit-native", "native-path-proven-without-python-compiler"]
        if self.data.get("verified_identity") != self.data["identity"] or not all(
            self.data["checks"].get(name) for name in required
        ):
            raise RuntimeError("verify installed bytes and complete smoke before measurement")
        samples = []
        for name, mode, relative in WORKLOADS:
            output = "/dev/null" if mode == "ir" else str(self.work / "timed-json")
            for backend in ("hosted", "native"):
                self.run(name + "-warm-" + backend, [self.cli, mode, ROOT / relative, "-o", output], backend, pin=True)
            for repeat in range(self.args.samples):
                order = ("hosted", "native") if repeat % 2 == 0 else ("native", "hosted")
                for backend in order:
                    row, _ = self.run(name + "-measure-" + backend,
                                      [self.cli, mode, ROOT / relative, "-o", output], backend, pin=True)
                    samples.append({"workload": name, "backend": backend, "repeat": repeat,
                                    **{key: row[key] for key in ("seconds", "peak_rss_kib", "user_seconds", "system_seconds")}})
                    save(self.out / "samples.json", samples)
        summary = {}
        for name, _, _ in WORKLOADS:
            rows = {backend: [r for r in samples if r["workload"] == name and r["backend"] == backend]
                    for backend in ("hosted", "native")}
            seconds = {backend: statistics.median(r["seconds"] for r in data) for backend, data in rows.items()}
            summary[name] = {"median_seconds": seconds, "speedup": seconds["hosted"] / seconds["native"],
                             "reduction_percent": 100 * (1 - seconds["native"] / seconds["hosted"]),
                             "median_peak_rss_kib": {b: statistics.median(r["peak_rss_kib"] for r in data)
                                                     for b, data in rows.items()}}
        if self.current_identity() != self.data["identity"]:
            raise RuntimeError("inputs changed during measurement")
        self.data["measurement"] = {"samples_per_backend": self.args.samples, "cpu": self.args.cpu,
                                     "loadavg_after": os.getloadavg(), "summary": summary,
                                     "scope": "installed CLI process startup included; warm page/runtime caches; AOT includes LLVM/backend/link"}
        self.flush()
        save(self.out / "summary.json", self.data["measurement"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("smoke", "verify", "measure"))
    parser.add_argument("--native-cli", type=Path, required=True)
    parser.add_argument("--source-cli", type=Path, required=True)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--time-command", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=4)
    parser.add_argument("--cpu", type=int, default=min(os.sched_getaffinity(0)))
    args = parser.parse_args()
    if args.samples < 4 or args.cpu not in os.sched_getaffinity(0):
        parser.error("need at least four samples and an allowed CPU")
    pilot = Pilot(args)
    getattr(pilot, args.phase)()


if __name__ == "__main__":
    main()
