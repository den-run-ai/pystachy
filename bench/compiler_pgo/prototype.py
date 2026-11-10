#!/usr/bin/env python3
"""Local LLVM IR PGO experiment for the native Pystachy compiler.

Independently implemented from documented LLVM flags. Serc's ordinary-build
output oracle and held-out training methodology inspired the experiment; no
Serc source, corpus, or fixture is included. This does not change defaults.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import statistics
import subprocess
import sys
import threading
import time


TRAINING = [
    ("self", "ir", "pystachy.py"),
    ("runtime", "rt", "runtime.py"),
    ("generics", "ir", "tests/programs/generics/templates.py"),
    ("recursive-generics", "ir", "tests/programs/generics/generic_recursive_members.py"),
    ("cleanup", "ir", "tests/programs/exceptions/exc_finally_deep.py"),
]

# These source entrypoints are never executed or used for profile generation.
HOLDOUT = [
    ("json-repair", "ir", "bench/json_repair/bench.py"),
    ("json-codec", "ir", "bench/json_repair/codec.py"),
    ("byte-bpe", "ir", "bench/pyperformance/bpe_tokeniser.py"),
    ("microgpt", "ir", "bench/microgpt/microgpt.py"),
    ("nbody", "ir", "bench/nbody.py"),
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    part = path.with_suffix(path.suffix + ".part")
    part.write_text(json.dumps(value, indent=2) + "\n")
    part.replace(path)


class Experiment:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.repo = args.repo.resolve()
        self.out = args.output.resolve()
        self.llvm = args.llvm.resolve()
        self.out.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.out / "manifest.json"
        self.data = (json.loads(self.manifest_path.read_text())
                     if self.manifest_path.exists() else {"commands": [], "checks": {}})
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("PYSTACHY_") and k != "LLVM_PROFILE_FILE"}
        self.env.update(PYSTACHY_HOME=str(self.repo), PYSTACHY_LLVM=str(self.llvm),
                        PYSTACHY_CACHE=str(self.out / "cache"))
        self.cpu = args.cpu
        self.source = self.source_identity()
        if "source" in self.data and self.source != self.data["source"]:
            raise RuntimeError("Compiler/runtime inputs changed; use a new output directory")
        self.data["source"] = self.source
        self.data["platform"] = {"platform": platform.platform(), "machine": platform.machine(),
                                 "affinity": sorted(os.sched_getaffinity(0))}
        toolchain = {
            name: {"path": str(self.llvm / name), "sha256": digest((self.llvm / name).resolve()),
                   "version": subprocess.check_output([str(self.llvm / name), "--version"],
                                                      env=self.env, text=True).splitlines()[0]}
            for name in ("clang", "opt", "llvm-profdata", "llvm-link")
        }
        shared = {}
        for name in ("clang", "opt", "llvm-profdata", "llvm-link"):
            linked = subprocess.check_output(["ldd", str(self.llvm / name)], env=self.env, text=True)
            for token in linked.split():
                if token.startswith("/") and Path(token).is_file():
                    resolved = Path(token).resolve()
                    if str(resolved) not in shared:
                        shared[str(resolved)] = digest(resolved)
        profile_runtime = Path(subprocess.check_output(
            [str(self.llvm / "clang"), "-print-file-name=libclang_rt.profile-x86_64.a"],
            env=self.env, text=True).strip())
        toolchain["shared_libraries"] = shared
        toolchain["profile_runtime"] = {"path": str(profile_runtime), "sha256": digest(profile_runtime)}
        if "toolchain" in self.data and toolchain != self.data["toolchain"]:
            raise RuntimeError("Toolchain changed; use a new output directory")
        self.data["toolchain"] = toolchain
        self.flush()

    def source_identity(self) -> dict:
        tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=self.repo).decode().split("\0")
        # All tracked compiler/runtime/library/data files, including notices.
        paths = [p for p in tracked if p and (p.startswith(("src/", "lib/", "ryu/", "mpz/", "data/", "ports/"))
                 or p in ("pystachy.py", "runtime.c", "runtime.py", "lljit.c", "pyembed.c", "pyext.c"))]
        untracked = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z", "src", "lib", "ryu", "mpz", "data", "ports"],
            cwd=self.repo).decode().strip("\0")
        if untracked:
            raise RuntimeError("Untracked compiler/runtime inputs: " + untracked.replace("\0", ", "))
        ignored = subprocess.check_output(
            ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "-z", "src", "lib", "ryu", "mpz", "data", "ports"],
            cwd=self.repo).decode().split("\0")
        hidden_sources = [p for p in ignored if p.endswith((".py", ".c", ".h"))]
        if hidden_sources:
            raise RuntimeError("Ignored import/include inputs: " + ", ".join(hidden_sources))
        return {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.repo).decode().strip(),
                "files": {p: digest(self.repo / p) for p in paths}}

    def flush(self) -> None:
        save(self.manifest_path, self.data)

    def unchanged_sources(self) -> None:
        if self.source_identity() != self.source:
            raise RuntimeError("Compiler/runtime input changed during the phase")

    def binary_identity(self, variant: str) -> str:
        expected = (self.data["ordinary_binary_sha256"] if variant == "ordinary"
                    else self.data[variant + "_binary"]["sha256"])
        actual = digest(self.out / variant)
        if actual != expected:
            raise RuntimeError("Binary changed: " + variant)
        return actual

    def profile_identity(self) -> str:
        actual = digest(self.out / "compiler.profdata")
        if actual != self.data["profile"]["sha256"]:
            raise RuntimeError("Training profile changed")
        return actual

    def verified_identity(self) -> dict:
        validated = {v: self.binary_identity(v) for v in ("ordinary", "pgo")}
        if validated != self.data.get("verified_binaries"):
            raise RuntimeError("Run verify for these exact compiler binaries before measuring")
        expected = [label + "-pgo-equality" for label, _, _ in TRAINING + HOLDOUT]
        expected += ["pgo-compiler-fixed-point", "pgo-runtime-fixed-point"]
        if not all(self.data["checks"].get(label, {}).get("equal") for label in expected):
            raise RuntimeError("Incomplete PGO equality/fixed-point checks")
        self.profile_identity()
        return validated

    def case_env(self, label: str) -> dict:
        return self.env | {"PYSTACHY_PATH": str(self.repo / "ports")} if label == "json-repair" else self.env

    def run(self, label: str, cmd: list[str], *, env: dict | None = None,
            timeout: int = 600, pin: bool = False, expected: int = 0,
            outputs: tuple[Path, ...] = ()) -> dict:
        # An exit-zero command must produce fresh evidence, not inherit a previous
        # invocation's IR, object, executable, profile or memory reading.
        for output in outputs:
            output.unlink(missing_ok=True)
        actual = (["taskset", "-c", str(self.cpu)] if pin else []) + [str(x) for x in cmd]
        logs = self.out / "logs"
        logs.mkdir(exist_ok=True)
        number = len(self.data["commands"])
        stdout = logs / f"{number:04d}-{label}.out"
        stderr = logs / f"{number:04d}-{label}.err"
        start = time.monotonic()
        with stdout.open("wb") as out, stderr.open("wb") as err:
            process = subprocess.Popen(actual, cwd=self.repo, env=env or self.env, stdout=out, stderr=err,
                                       start_new_session=True)
            # Blocking wait4 avoids polling quantization on short frontend jobs.
            def terminate_owned_group() -> None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            timer = threading.Timer(timeout, terminate_owned_group)
            timer.daemon = True
            timer.start()
            try:
                _, status, usage = os.wait4(process.pid, 0)
                process.returncode = os.waitstatus_to_exitcode(status)
            finally:
                timer.cancel()
        result = {"label": label, "command": actual, "seconds": time.monotonic() - start,
                  "returncode": process.returncode, "peak_rss_kib": usage.ru_maxrss,
                  "user_seconds": usage.ru_utime, "system_seconds": usage.ru_stime,
                  "stdout": str(stdout), "stderr": str(stderr),
                  "stdout_sha256": digest(stdout), "stderr_sha256": digest(stderr)}
        self.data["commands"].append(result)
        self.flush()
        if process.returncode != expected:
            raise RuntimeError(f"{label}: exit {process.returncode}; see {stderr}")
        for output in outputs:
            if not output.is_file() or output.stat().st_size == 0:
                raise RuntimeError(f"{label}: missing or empty output: {output}")
        return result

    def compare(self, label: str, left: Path, right: Path) -> None:
        wanted, actual = left.read_bytes(), right.read_bytes()
        same = bool(wanted) and wanted == actual
        self.data["checks"][label] = {"equal": same, "sha256": digest(left),
                                       "candidate_sha256": digest(right)}
        self.flush()
        if not same:
            raise RuntimeError(f"Output changed: {label}")

    def capture(self) -> None:
        self.inputs(TRAINING + HOLDOUT)
        baseline = self.repo / "pystachy"
        if not baseline.is_file():
            raise RuntimeError("Run unmodified make first (compiler and runtime fixed points)")
        wrappers = self.out / "capture-tools"
        wrappers.mkdir(exist_ok=True)
        for binary in self.llvm.iterdir():
            if binary.is_file() and binary.name != "clang":
                target = wrappers / binary.name
                if not target.exists():
                    target.symlink_to(binary)
        capture = self.out / "compiler-linked.bc"
        script = ("#!" + sys.executable + "\nimport os, pathlib, shutil, sys\n"
                  "args = sys.argv[1:]\n"
                  "for arg in args:\n"
                  "    if pathlib.Path(arg).name == 'prog.bc' and '-emit-llvm' in args:\n"
                  "        shutil.copyfile(arg, " + repr(str(capture)) + ")\n"
                  "os.execv(" + repr(str(self.llvm / "clang")) + ", ['clang'] + args)\n")
        (wrappers / "clang").write_text(script)
        (wrappers / "clang").chmod(0o755)
        env = self.env | {"PYSTACHY_LLVM": str(wrappers)}
        self.run("capture-ordinary", [str(baseline), "build", "pystachy.py", "-o",
                 str(self.out / "ordinary"), "--emit-ir", str(self.out / "ordinary.ll")], env=env,
                 outputs=(self.out / "ordinary", self.out / "ordinary.ll", capture))
        self.compare("ordinary-compiler-fixed-point", self.repo / "build/stage1.ll", self.out / "ordinary.ll")
        inspection = self.run("inspect-captured-input", [str(self.llvm / "llvm-dis"), str(capture), "-o", "-"])
        linked_ir = Path(inspection["stdout"]).read_text()
        if "llvm.instrprof" in linked_ir or "__llvm_prf" in linked_ir:
            raise RuntimeError("Captured compiler bitcode already contains profile instrumentation")
        self.data["linked_bitcode_sha256"] = digest(capture)
        self.data["bootstrap_binary_sha256"] = digest(baseline)
        self.data["ordinary_binary_sha256"] = digest(self.out / "ordinary")
        self.flush()

    def build(self, variant: str) -> None:
        linked = self.out / "compiler-linked.bc"
        if digest(linked) != self.data["linked_bitcode_sha256"]:
            raise RuntimeError("Captured bitcode drift")
        if variant == "pgo":
            self.profile_identity()
        flags = (["-fprofile-generate"] if variant == "instrumented" else
                 ["-fprofile-use=" + str(self.out / "compiler.profdata")])
        optimized = self.out / (variant + ".opt.bc")
        late = self.out / (variant + ".late.bc")
        obj = self.out / (variant + ".o")
        clang, opt = str(self.llvm / "clang"), str(self.llvm / "opt")
        result = self.run(variant + "-optimize", [clang, "-O2", "-c", "-emit-llvm", str(linked),
                 "-o", str(optimized), "-Wno-unused-command-line-argument"] + flags, outputs=(optimized,))
        if Path(result["stderr"]).read_bytes():
            raise RuntimeError("Unexpected optimization diagnostic; inspect before accepting " + variant)
        self.run(variant + "-late-inline", [opt, "-passes=forceattrs,forceattrs,always-inline",
                 "-force-remove-attribute=pys_new:optnone", "-force-remove-attribute=pys_new:noinline",
                 "-force-attribute=pys_new:alwaysinline", str(optimized), "-o", str(late)], outputs=(late,))
        self.run(variant + "-codegen", [clang, "-O2", "-c", "-Xclang", "-disable-llvm-passes",
                 str(late), "-o", str(obj), "-Wno-unused-command-line-argument"], outputs=(obj,))
        self.run(variant + "-link", [clang, str(obj), "-o", str(self.out / variant), "-lm"]
                 + (["-fprofile-generate"] if variant == "instrumented" else []), outputs=(self.out / variant,))
        self.data[variant + "_binary"] = {"sha256": digest(self.out / variant),
                                          "bytes": (self.out / variant).stat().st_size}
        self.flush()

    def inputs(self, cases: list[tuple[str, str, str]]) -> None:
        records = {label: {"command": mode, "path": path, "sha256": digest(self.repo / path)}
                   for label, mode, path in cases}
        existing = self.data.get("inputs", {})
        for label, record in records.items():
            if label in existing and existing[label] != record:
                raise RuntimeError("Input drift: " + label)
        self.data["inputs"] = existing | records
        self.flush()

    def train(self) -> None:
        self.binary_identity("ordinary")
        self.binary_identity("instrumented")
        self.inputs(TRAINING)
        raw = self.out / "raw"
        raw.mkdir(exist_ok=True)
        if list(raw.glob("*.profraw")):
            raise RuntimeError("Refusing to merge stale training profiles; use a fresh output")
        oracle = self.out / "oracle"
        oracle.mkdir(exist_ok=True)
        for label, mode, path in TRAINING:
            want = oracle / (label + ".ll")
            got = self.out / (label + ".instrumented.ll")
            control = self.run(label + "-ordinary", [str(self.out / "ordinary"), mode, path, "-o", str(want)],
                               outputs=(want,))
            if Path(control["stderr"]).read_bytes():
                raise RuntimeError("Unexpected ordinary diagnostic " + label)
            self.data.setdefault("oracle", {})[label] = digest(want)
            result = self.run(label + "-train", [str(self.out / "instrumented"), mode, path, "-o", str(got)],
                             env=self.env | {"LLVM_PROFILE_FILE": str(raw / (label + "-%m-%p.profraw"))},
                             outputs=(got,))
            if Path(result["stderr"]).read_bytes():
                raise RuntimeError("Unexpected diagnostic while training " + label)
            self.compare(label + "-instrumented-equality", want, got)
        profiles = sorted(raw.glob("*.profraw"))
        if len(profiles) != len(TRAINING):
            raise RuntimeError("Training profile count does not match inputs")
        self.run("merge-profile", [str(self.llvm / "llvm-profdata"), "merge", "-o",
                 str(self.out / "compiler.profdata")] + [str(p) for p in profiles],
                 outputs=(self.out / "compiler.profdata",))
        result = self.run("profile-counts", [str(self.llvm / "llvm-profdata"), "show", "--all-functions",
                         "--counts", str(self.out / "compiler.profdata")])
        profile = Path(result["stdout"]).read_text()
        records = re.findall(r"^  (.+):\n    Hash: [^\n]+\n    Counters: [^\n]+\n    Block counts: \[([^]]*)\]",
                             profile, re.MULTILINE)
        # The optimizer can inline compile_program before placing counters, so
        # require executed functions across compiler stages rather than one name.
        covered = {}
        for stage in ("lexer", "parser", "gen", "lowering"):
            live = {name: max(int(n) for n in counts.split(", "))
                    for name, counts in records if "$" + stage + "$" in name and counts}
            covered[stage] = {name: count for name, count in live.items() if count > 0}
        if "Instrumentation level: IR" not in profile or not all(covered.values()):
            raise RuntimeError("Profile does not demonstrate IR instrumentation of compiler functions")
        self.data["profile"] = {"sha256": digest(self.out / "compiler.profdata"),
                                 "raw": {p.name: digest(p) for p in profiles},
                                 "total_functions": len(records),
                                 "executed_compiler_stage_functions": {k: len(v) for k, v in covered.items()},
                                 "stage_counter_examples": {k: max(v.items(), key=lambda item: item[1])
                                                            for k, v in covered.items()}}
        self.binary_identity("ordinary")
        self.binary_identity("instrumented")
        self.flush()

    def verify(self) -> None:
        self.data.pop("verified_binaries", None)
        self.flush()
        validated = {v: self.binary_identity(v) for v in ("ordinary", "pgo")}
        self.profile_identity()
        self.inputs(TRAINING + HOLDOUT)
        oracle = self.out / "oracle"
        oracle.mkdir(exist_ok=True)
        for label, mode, path in TRAINING + HOLDOUT:
            want, got = oracle / (label + ".ll"), self.out / (label + ".pgo.ll")
            if not want.exists():
                control = self.run(label + "-ordinary", [str(self.out / "ordinary"), mode, path, "-o", str(want)],
                                   env=self.case_env(label), outputs=(want,))
                if Path(control["stderr"]).read_bytes():
                    raise RuntimeError("Unexpected ordinary diagnostic " + label)
                self.data.setdefault("oracle", {})[label] = digest(want)
            if digest(want) != self.data["oracle"][label]:
                raise RuntimeError("Ordinary oracle IR changed: " + label)
            result = self.run(label + "-pgo", [str(self.out / "pgo"), mode, path, "-o", str(got)],
                              env=self.case_env(label), outputs=(got,))
            if Path(result["stderr"]).read_bytes():
                raise RuntimeError("Unexpected PGO diagnostic " + label)
            self.compare(label + "-pgo-equality", want, got)
        self.compare("pgo-compiler-fixed-point", self.repo / "build/stage1.ll", self.out / "self.pgo.ll")
        self.compare("pgo-runtime-fixed-point", self.repo / "build/rt1.ll", self.out / "runtime.pgo.ll")
        if validated != {v: self.binary_identity(v) for v in ("ordinary", "pgo")}:
            raise RuntimeError("Compiler binaries changed during verification")
        self.unchanged_sources()
        self.data["verified_binaries"] = validated
        self.flush()

    def measure(self) -> None:
        validated = self.verified_identity()
        self.inputs(TRAINING + HOLDOUT)
        samples = []
        for label, mode, path in TRAINING[:2] + HOLDOUT:
            for variant in ("ordinary", "pgo"):
                self.run(label + "-warm-" + variant, [str(self.out / variant), mode, path, "-o", "/dev/null"],
                         pin=True, env=self.case_env(label))
            for repeat in range(self.args.samples):
                order = ("ordinary", "pgo") if repeat % 2 == 0 else ("pgo", "ordinary")
                for variant in order:
                    row = self.run(label + "-measure-" + variant, [str(self.out / variant), mode, path,
                                   "-o", "/dev/null"], pin=True, env=self.case_env(label))
                    samples.append({"workload": label, "variant": variant, "repeat": repeat,
                                    **{k: row[k] for k in ("seconds", "peak_rss_kib", "user_seconds", "system_seconds")}})
                    save(self.out / "samples.json", samples)
        summary = {}
        for label in {r["workload"] for r in samples}:
            rows = {v: [r for r in samples if r["workload"] == label and r["variant"] == v]
                    for v in ("ordinary", "pgo")}
            times = {v: statistics.median(r["seconds"] for r in data) for v, data in rows.items()}
            summary[label] = {"median_seconds": times, "speedup": times["ordinary"] / times["pgo"],
                              "reduction_percent": 100 * (1 - times["pgo"] / times["ordinary"]),
                              "median_peak_rss_kib": {v: statistics.median(r["peak_rss_kib"] for r in data)
                                                       for v, data in rows.items()}}
        self.unchanged_sources()
        self.data["measurement"] = {"cpu": self.cpu, "samples_per_variant": self.args.samples,
                                     "summary": summary, "loadavg_after": os.getloadavg(),
                                     "verified_binaries": validated,
                                     "harness_sha256": digest(Path(__file__)),
                                     "memory_note": "wait4 RSS includes pre-exec parent RSS; use the separate GNU time memory phase",
                                     "scope": "native compiler frontend plus process startup and IR output; warm page cache"}
        if validated != {v: self.binary_identity(v) for v in ("ordinary", "pgo")}:
            raise RuntimeError("Compiler binaries changed during measurement")
        self.flush()
        save(self.out / "summary.json", self.data["measurement"])

    def memory(self) -> None:
        validated = self.verified_identity()
        self.inputs(TRAINING + HOLDOUT)
        meter = self.args.time_tool.resolve()
        readings = []
        for label, mode, path in TRAINING[:2] + HOLDOUT:
            for variant in ("ordinary", "pgo"):
                rss = self.out / (label + "-" + variant + ".rss")
                self.run(label + "-memory-" + variant, [str(meter), "-q", "-f", "%M", "-o", str(rss),
                         str(self.out / variant), mode, path, "-o", "/dev/null"],
                         pin=True, env=self.case_env(label), outputs=(rss,))
                readings.append({"workload": label, "variant": variant,
                                 "peak_rss_kib": int(rss.read_text().strip())})
        if validated != {v: self.binary_identity(v) for v in ("ordinary", "pgo")}:
            raise RuntimeError("Compiler binaries changed during memory measurement")
        self.unchanged_sources()
        self.data["memory"] = {"method": "GNU time child peak RSS, separate from timed cohort",
                               "samples_per_variant": 1, "tool": str(meter), "tool_sha256": digest(meter),
                               "verified_binaries": validated, "readings": readings}
        self.flush()
        save(self.out / "memory.json", self.data["memory"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["capture", "instrument", "train", "optimize", "verify", "measure", "memory"])
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--cpu", type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument("--time-tool", type=Path, default=Path("/usr/bin/time"))
    args = parser.parse_args()
    if args.samples < 3:
        parser.error("Use at least three interleaved samples")
    if args.cpu not in os.sched_getaffinity(0):
        parser.error("CPU is outside allowed affinity")
    experiment = Experiment(args)
    {"capture": experiment.capture, "instrument": lambda: experiment.build("instrumented"),
     "train": experiment.train, "optimize": lambda: experiment.build("pgo"),
     "verify": experiment.verify, "measure": experiment.measure, "memory": experiment.memory}[args.phase]()
    experiment.unchanged_sources()


if __name__ == "__main__":
    main()
