"""Paired before/after JIT/AOT timings with exact CPython checksum validation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import time

SOURCE = Path(__file__).with_name("workload.py").resolve()
INT_TEXT = Path(__file__).with_name("int_text.py").resolve()
REDUCTIONS = Path(__file__).with_name("reductions.py").resolve()
NUMERIC = Path(__file__).with_name("numeric.py").resolve()
INTEGERS = Path(__file__).with_name("integers.py").resolve()
# Keep the small arithmetic kernels long enough to measure without launch time.
COUNTS = {"scalar": 120000000, "range": 60000000, "power": 60000000,
          "sum-float": 5000, "sum-int": 5000, "reduction": 5000, "ascii": 5000, "unicode": 5000,
          "str-int": 20000000, "str-int-short": 20000000, "int-str": 20000000, "int-str-short": 20000000,
          "int-str-hex": 20000000, "int-str-padded": 20000000,
          "ints-any-all": 400000, "ints-any-all-short": 200000000, "ints-sum-float": 400000,
          "join": 800000, "join-bytes": 400000, "join-slice": 1200000, "path-join": 60000000,
          "hypot": 60000000, "hypot-3": 30000000, "dist-3": 40000000, "dist-64": 4000000, "fma": 150000000,
          "powmod": 3000000, "powmod-31": 3500000, "round-int": 70000000, "ints-sum": 900000,
          "floordiv": 50000000, "modulo": 50000000, "lshift": 50000000, "rshift": 50000000,
          "bit-length": 50000000, "bit-count": 50000000, "idiv-small": 50000000, "idiv-wide": 20000000}
# The cases of a later migration have a source of their own, so that workload.py keeps the hash
# that the first recorded report names.
INT_TEXT_CASES = ("str-int", "str-int-short", "int-str", "int-str-short", "int-str-hex", "int-str-padded")
REDUCTION_CASES = ("ints-any-all", "ints-any-all-short", "ints-sum-float", "join", "join-bytes", "join-slice", "path-join")
NUMERIC_CASES = ("hypot", "hypot-3", "dist-3", "dist-64", "fma", "powmod", "powmod-31", "round-int", "ints-sum")
INTEGER_CASES = ("floordiv", "modulo", "lshift", "rshift", "bit-length", "bit-count", "idiv-small", "idiv-wide")
SOURCES = dict.fromkeys(COUNTS, SOURCE)
for source, workload_cases in ((INT_TEXT, INT_TEXT_CASES), (REDUCTIONS, REDUCTION_CASES),
                               (NUMERIC, NUMERIC_CASES), (INTEGERS, INTEGER_CASES)):
    SOURCES.update(dict.fromkeys(workload_cases, source))


def run(command, cwd, env):
    start = time.perf_counter()
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True,
                            timeout=600, check=True)
    return {"wall_seconds": time.perf_counter() - start,
            "stdout": result.stdout, "stderr": result.stderr}


def timed(record, expected):
    fields = record["stdout"].split()
    if len(fields) != 2 or fields[0] != expected:
        raise ValueError(f"checksum/output mismatch: {record['stdout']!r}, expected {expected}")
    elapsed = float(fields[1])
    if not 0.0 < elapsed < float("inf"):
        raise ValueError("invalid in-process time")
    return {**record, "kernel_seconds": elapsed}


def gc_record(record, expected):
    result = timed(record, expected)
    rows = re.findall(r"^gc: (\d+) collections, ([0-9.]+) ms; heap peak ([0-9.]+) MiB; live ([0-9.]+) MiB at the last$",
                      result["stderr"], re.M)
    if len(rows) != 1:
        raise ValueError("expected exactly one AOT program GC summary")
    collections, milliseconds, peak, live = rows[0]
    result["managed_heap"] = {"collections": int(collections), "collection_ms": float(milliseconds),
                              "peak_mib_rounded": float(peak), "live_mib_rounded": float(live)}
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata(root, compiler, env):
    paths = [root / "pystachy.py", root / "runtime.c", root / "runtime.py"]
    paths += sorted((root / "src").rglob("*.py"))
    return {"commit": run(["git", "rev-parse", "HEAD"], root, env)["stdout"].strip(),
            "status": run(["git", "status", "--porcelain"], root, env)["stdout"],
            "compiler_sha256": digest(compiler),
            "source_sha256": {str(p.relative_to(root)): digest(p) for p in paths}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True, help="baseline repository with ./pystachy")
    parser.add_argument("--after", type=Path, required=True, help="candidate repository with ./pystachy")
    parser.add_argument("--pairs", type=int, default=7)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--cases", nargs="+", choices=COUNTS, default=list(COUNTS))
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    if args.pairs < 1 or not 0.0 < args.scale < float("inf"):
        parser.error("pairs and scale must be positive")
    if not os.environ.get("PYSTACHY_LLVM"):
        parser.error("set PYSTACHY_LLVM to the matching LLVM toolchain's bin directory")
    # Fail closed even if metadata discovery, the first build or the oracle fails.
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps({"complete": False, "stage": "initializing"}) + "\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env["PYSTACHY_LLVM"] = str(Path(os.environ["PYSTACHY_LLVM"]).expanduser().resolve())
    roots = {"before": args.before.resolve(), "after": args.after.resolve()}
    compilers = {label: root / "pystachy" for label, root in roots.items()}
    report = {"complete": False, "requested_cases": args.cases, "load_average_at_start": os.getloadavg(),
              "platform": platform.platform(), "python": sys.version,
              "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
              "workload_sha256": {path.name: digest(path) for path in sorted({SOURCES[case] for case in args.cases})},
              "pairs": args.pairs,
              "environment": {k: v for k, v in env.items() if k.startswith("PYSTACHY_")},
              "sources": {label: metadata(root, compilers[label], env) for label, root in roots.items()},
              "cases": {}}
    llvm = Path(env["PYSTACHY_LLVM"])
    report["llvm"] = run([str(llvm / "clang"), "--version"], roots["after"], env)["stdout"]
    # Compilation and cache warmup precede all measured pairs. Run serially on a
    # pinned CPU (taskset); never overlap this controller with native builds.
    with tempfile.TemporaryDirectory(prefix="runtime-subset-") as scratch:
        executables = {}
        for label, root in roots.items():
            report["sources"][label]["aot_build"] = {}
            report["sources"][label]["executable_bytes"] = {}
            for source in sorted({SOURCES[case] for case in args.cases}):
                exe = Path(scratch) / f"{label}-{source.stem}"
                build = run([str(compilers[label]), "build", str(source), "-o", str(exe)], root, env)
                report["sources"][label]["aot_build"][source.name] = build
                report["sources"][label]["executable_bytes"][source.name] = exe.stat().st_size
                executables[label, source] = exe
        for case in args.cases:
            source = SOURCES[case]
            count = max(1, int(COUNTS[case] * args.scale))
            params = [case, str(count)]
            oracle = run([sys.executable, str(source), *params], roots["after"], env)
            expected = oracle["stdout"].split()[0]
            timed(oracle, expected)
            results = {"count": count, "checksum": expected, "cpython": oracle, "modes": {}}
            for mode in ("aot", "jit"):
                commands = {label: ([str(executables[label, source])] if mode == "aot" else
                                    [str(compilers[label]), "run", str(source)]) + params
                            for label in roots}
                for label in roots:
                    timed(run(commands[label], roots[label], env), expected)
                pairs = []
                for repeat in range(args.pairs):
                    pair = {}
                    for label in (["before", "after"] if repeat % 2 == 0 else ["after", "before"]):
                        pair[label] = timed(run(commands[label], roots[label], env), expected)
                    pair["ratio"] = pair["after"]["kernel_seconds"] / pair["before"]["kernel_seconds"]
                    pairs.append(pair)
                results["modes"][mode] = {"pairs": pairs,
                                          "median_ratio_after_over_before": statistics.median(p["ratio"] for p in pairs)}
            results["gc"] = {label: gc_record(run([str(executables[label, source]), *params], root,
                                                    {**env, "PYSTACHY_GC": "stats"}), expected)
                             for label, root in roots.items()}
            report["cases"][case] = results
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(report, indent=2) + "\n")
            print(case, {m: r["median_ratio_after_over_before"] for m, r in results["modes"].items()}, flush=True)
        report["complete"] = True
        args.json.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
