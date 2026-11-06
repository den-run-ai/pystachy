"""Reproduce original/adapted CPython and native byte-BPE stage measurements.

This CPython controller uses no third-party packages. All modes execute the same
driver; the original mode imports unchanged kernels from the pinned upstream file.
Fresh temporary binaries and exact full-output checks guard every native sample.
"""
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BENCH = ROOT / "bench/pyperformance"
UPSTREAM_SHA256 = "c7255345499e118181785370b0996e8cc1056491b9678b3fbeb02421e3f9b2df"
CORPUS_SHA256 = "6607193e67b7b459d082f5f2aea724e470615643d63ad2e205123b3076223da4"
PATTERN = r"'s|'t|'re|'ve|'m|'ll|'d| ?[a-zA-Z]+| ?\d+| ?[^\sa-zA-Z\d]+|\s+(?!\S)|\s+"
STAGES = ("train", "encode", "decode")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original_module():
    """Keep exact kernel source text; omit only the upstream pyperf runner/setup."""
    source = HERE / "upstream/bpe_tokeniser.py"
    if digest(source) != UPSTREAM_SHA256:
        raise ValueError("upstream source SHA-256 mismatch")
    text = source.read_text(encoding="utf-8")
    wanted = {"SimpleBytePairEncoding", "bpe_encode", "bpe_train"}
    nodes = [n for n in ast.parse(text).body
             if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in wanted]
    if {n.name for n in nodes} != wanted or len(nodes) != len(wanted):
        raise ValueError("missing or duplicate upstream kernels")
    return ("from __future__ import annotations\nimport collections\nimport re\n\n" +
            "\n\n".join(ast.get_source_segment(text, node) for node in nodes) +
            f"\n\nBPE_PATTERN = {PATTERN!r}\n")


def parse_times(stderr):
    rows = stderr.splitlines()
    if len(rows) != len(STAGES):
        raise ValueError(f"expected exactly three stage timing rows: {stderr[-400:]!r}")
    result = {}
    for row, stage in zip(rows, STAGES, strict=True):
        fields = row.split()
        if len(fields) != 2 or fields[0] != stage:
            raise ValueError(f"invalid {stage} timing row: {row!r}")
        value = float(fields[1])
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"nonpositive or nonfinite {stage} time")
        result[stage] = value
    return result


def run(command, env, timeout):
    """Bound the process group and retain wait4 plus Linux executable RSS samples.

    wait4 can retain the launcher's pre-exec high-water mark. Linux VmHWM samples
    start only after the child has installed its requested command line; these
    describe the main executable and exclude compiler subprocesses.
    File-backed output avoids pipe deadlocks and leaves no reusable executable.
    """
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as error:
        started = time.perf_counter()
        proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=output,
                                stderr=error, start_new_session=True)
        installed = False
        sampled_rss = None
        expected_cmdline = [os.fsencode(part) for part in command]
        try:
            while True:
                pid, status, usage = os.wait4(proc.pid, os.WNOHANG)
                if pid:
                    proc.returncode = os.waitstatus_to_exitcode(status)
                    break
                if sys.platform.startswith("linux"):
                    try:
                        proc_dir = Path("/proc") / str(proc.pid)
                        if not installed:
                            installed = (proc_dir / "cmdline").read_bytes().split(b"\0")[:-1] == expected_cmdline
                        if installed:
                            for line in (proc_dir / "status").read_text().splitlines():
                                if line.startswith("VmHWM:"):
                                    sampled_rss = max(sampled_rss or 0, int(line.split()[1]))
                    except (OSError, ValueError):
                        pass  # The process can exit or exec between /proc reads.
                if time.perf_counter() - started > timeout:
                    raise TimeoutError(f"timeout: {shlex.join(command)}")
                time.sleep(0.005)
        except BaseException:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            _, status, _ = os.wait4(proc.pid, 0)
            proc.returncode = os.waitstatus_to_exitcode(status)
            raise
        elapsed = time.perf_counter() - started
        output.seek(0)
        error.seek(0)
        stdout = output.read().decode("utf-8")
        stderr = error.read().decode("utf-8")
    if proc.returncode:
        raise RuntimeError(f"exit {proc.returncode}: {shlex.join(command)}\n{stderr[-3000:]}")
    return {"command": command, "wall_seconds": elapsed,
            "cpu_seconds": usage.ru_utime + usage.ru_stime,
            "peak_rss_kib": usage.ru_maxrss / 1024 if sys.platform == "darwin" else usage.ru_maxrss,
            "sampled_main_rss_kib": sampled_rss,
            "stdout": stdout, "stderr": stderr,
            "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest()}


def checked_sample(record, expected, encode_loops, decode_loops):
    if record["stdout"] != expected:
        raise ValueError("complete vocabulary/token/decoded output differs from original CPython")
    times = parse_times(record["stderr"])
    record.update(train_seconds=times["train"],
                  encode_seconds=times["encode"] / encode_loops,
                  decode_seconds=times["decode"] / decode_loops,
                  outside_timers_seconds=record["wall_seconds"] - sum(times.values()))
    del record["stdout"]
    return record


def summary(records):
    keys = ["train_seconds", "encode_seconds", "decode_seconds", "wall_seconds",
            "outside_timers_seconds", "cpu_seconds", "peak_rss_kib"]
    if all(r["sampled_main_rss_kib"] is not None for r in records):
        keys.append("sampled_main_rss_kib")
    return {key: {"median": statistics.median(r[key] for r in records),
                  "min": min(r[key] for r in records), "max": max(r[key] for r in records)}
            for key in keys}


def provenance(compiler, env, paths):
    def info(command):
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                text=True, timeout=30, check=True)
        return result.stdout.strip()
    sources = [ROOT / "pystachy.py", ROOT / "runtime.py", ROOT / "runtime.c"]
    sources += sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "lib").rglob("*.py"))
    sources += [p for part in ("ryu", "mpz") for p in sorted((ROOT / part).glob("*"))
                if p.suffix in (".c", ".h")]
    llvm = Path(env.get("PYSTACHY_LLVM", ""))
    return {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "git_revision": info(["git", "rev-parse", "HEAD"]),
            "git_status": info(["git", "status", "--porcelain"]),
            "python": sys.version, "platform": platform.platform(),
            "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "cpu_model": next((s.split(":", 1)[1].strip() for s in Path("/proc/cpuinfo").read_text().splitlines()
                               if s.startswith("model name")), None) if Path("/proc/cpuinfo").exists() else None,
            "load_average": os.getloadavg(), "compiler_command": compiler,
            "compiler_binary_sha256": digest(Path(compiler[0])) if Path(compiler[0]).is_file() else None,
            "llvm": {name: info([str(llvm / name) if str(llvm) != "." else name, "--version"])
                     for name in ("clang", "opt", "lli")},
            "environment": {k: v for k, v in env.items() if k.startswith("PYSTACHY_") or k == "PYTHONHASHSEED"},
            "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in sorted(set(sources + paths))},
            "rss_definition": "wait4 process-family maximum, including possible pre-exec launcher high-water mark; KiB",
            "sampled_rss_definition": "Linux main-process VmHWM after requested command installed, sampled every ~5 ms; excludes children; KiB"}


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"))
    parser.add_argument("--processes", type=positive, default=5)
    parser.add_argument("--encode-loops", type=positive, default=50)
    parser.add_argument("--decode-loops", type=positive, default=200)
    parser.add_argument("--cpu", type=int, help="pin controller and children to one available CPU")
    parser.add_argument("--gc-min", type=positive, help="optional per-workload MiB threshold; default unchanged")
    parser.add_argument("--smoke", action="store_true", help="one small process per mode, correctness only")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--json", type=Path, default=ROOT / "build/byte-bpe.json")
    args = parser.parse_args(argv)
    compiler = shlex.split(args.compiler)
    if not compiler or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("compiler must be nonempty and timeout positive and finite")
    compiler_path = shutil.which(compiler[0])
    if compiler_path is None:
        parser.error("compiler executable was not found")
    compiler[0] = str(Path(compiler_path).resolve())
    if not hasattr(os, "wait4"):
        parser.error("process RSS measurements require a POSIX host with wait4")
    if args.cpu is not None:
        if not hasattr(os, "sched_getaffinity") or args.cpu not in os.sched_getaffinity(0):
            parser.error("--cpu must be an available CPU on a host supporting affinity")
        os.sched_setaffinity(0, {args.cpu})
    if args.smoke:
        args.processes, args.encode_loops, args.decode_loops = 1, 1, 1
    # A clean default is needed for interpretable compiler/GC comparisons. Preserve only
    # the selected LLVM location; other experimental compiler settings are not inherited.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PYSTACHY_") and k not in ("PYTHONPATH", "PYTHONHOME")}
    env.update(PYTHONHASHSEED="0", PYSTACHY_HOME=str(ROOT), PYSTACHY_PROGRAM_CACHE="0",
               PYSTACHY_PATH=str(BENCH), PYTHONPATH=str(BENCH), PYTHONDONTWRITEBYTECODE="1")
    if "PYSTACHY_LLVM" in os.environ:
        env["PYSTACHY_LLVM"] = os.environ["PYSTACHY_LLVM"]
    if args.gc_min:
        env["PYSTACHY_GC_MIN"] = str(args.gc_min)
    report = {"status": "running", "smoke": args.smoke, "runs": {}}
    args.json.parent.mkdir(parents=True, exist_ok=True)

    def save():
        temporary = args.json.with_name(args.json.name + ".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.json)

    save()
    try:
        corpus = BENCH / "data/frankenstein_intro.txt"
        if digest(corpus) != CORPUS_SHA256:
            raise ValueError("corpus SHA-256 mismatch")
        original = original_module()
        paths = [corpus, BENCH / "bpe_tokeniser.py", HERE / "stages.py",
                 HERE / "demo.py", Path(__file__).resolve(), HERE / "upstream/bpe_tokeniser.py"]
        report["metadata"] = provenance(compiler, env, paths)
        with tempfile.TemporaryDirectory(prefix="pystachy-byte-bpe-") as temp:
            directory = Path(temp)
            env["PYSTACHY_CACHE"] = str(directory / "runtime-cache")
            original_dir = directory / "original"
            original_dir.mkdir()
            (original_dir / "bpe_tokeniser.py").write_text(original, encoding="utf-8")
            original_env = dict(env, PYTHONPATH=str(original_dir))
            vocab_size = 1024
            if args.smoke:
                corpus = directory / "tiny.txt"
                corpus.write_text("banana bandana banana! 日本語 🦉\tÆ É Ġ\n" * 2, encoding="utf-8")
                vocab_size = 264
            runargs = [str(corpus), str(vocab_size), str(args.encode_loops), str(args.decode_loops)]
            source, executable = str(HERE / "stages.py"), str(directory / "byte-bpe-stages")
            commands = {"original_cpython": [sys.executable, source, *runargs],
                        "adapted_cpython": [sys.executable, source, *runargs],
                        "jit": compiler + ["run", source, *runargs], "aot": [executable, *runargs]}
            oracle = run(commands["original_cpython"], original_env, args.timeout)
            parse_times(oracle["stderr"])
            expected = oracle["stdout"]
            if len(expected.splitlines()) != 4:
                raise ValueError("oracle did not emit all four complete state rows")
            report["oracle"] = {"stdout": expected, "sha256": oracle["stdout_sha256"]}
            report["workload"] = {"corpus_bytes": corpus.stat().st_size, "corpus_sha256": digest(corpus),
                                  "vocab_size": vocab_size, "encode_loops": args.encode_loops,
                                  "decode_loops": args.decode_loops, "processes": args.processes}
            # Explicitly warm each path. A fresh binary is built in a unique directory;
            # no failed compilation can reuse an executable from a previous invocation.
            warm = directory / "warm.py"
            warm.write_text("print(1)\n")
            report["runtime_prime"] = run(compiler + ["run", str(warm)], env, args.timeout)
            report["aot_build"] = run(compiler + ["build", source, "-o", executable], env, args.timeout)
            report["aot_binary_sha256"] = digest(Path(executable))
            report["aot_binary_bytes"] = Path(executable).stat().st_size
            modes = list(commands)
            report["runs"] = {mode: [] for mode in modes}
            for repeat in range(args.processes):
                for mode in modes[repeat % len(modes):] + modes[:repeat % len(modes)]:
                    record = run(commands[mode], original_env if mode == "original_cpython" else env, args.timeout)
                    report["runs"][mode].append(checked_sample(record, expected, args.encode_loops, args.decode_loops))
                    save()
                    print(f"{repeat + 1}/{args.processes} {mode}: complete output matches", flush=True)
            report["summary"] = {mode: summary(rows) for mode, rows in report["runs"].items()}
        for name, value in report["metadata"]["source_sha256"].items():
            if digest(ROOT / name) != value:
                raise ValueError(f"source changed during measurements: {name}")
        if digest(Path(compiler[0])) != report["metadata"]["compiler_binary_sha256"]:
            raise ValueError("compiler executable changed during measurements")
        report["status"] = "passed"
        save()
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        save()
        raise
    print(f"Saved {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
