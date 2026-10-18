"""Correctness-gated JSON parsing/processing benchmark; see docs/json-benchmark.md.

No downloads or performance thresholds. The source-written guarded mode is a
control, not a claim of automatic profile-guided or online specialization.
"""
import argparse
import json
import math
import os
from pathlib import Path
import platform
import shlex
import statistics
import sys
import tempfile
import time

from bench_extended import digest, execute, positive, summary

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/json_records.py"
PROFILES = ("skewed", "mixed", "changing")


def fixture(records, profile):
    """Deterministic input with skew, broad alternatives and a late phase shift."""
    result = []
    for index in range(records):
        slot = index % 100
        if profile == "mixed" or profile == "changing" and index >= records // 2:
            slot = (index % 8) + 92
        record = {"id": index, "details": {
            "name": "event-" + str(index) + "-é雪🚀",
            "tags": ["api", "paid" if index % 2 else "pending", "地域"],
        }}
        amount = index % 1000
        if slot < 92:
            record["amount"] = amount
        elif slot < 94:
            record["amount"] = amount + 0.25
        elif slot == 94:
            record["amount"] = None
        elif slot == 95:
            pass  # Missing field: .get() must preserve the null fallback.
        elif slot == 96:
            record["amount"] = "pending"
        elif slot == 97:
            record["amount"] = True
        elif slot == 98:
            record["amount"] = [amount, None]
        else:
            record["amount"] = {"units": amount}
        result.append(record)
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def parse_output(output, samples, expected=None):
    lines = [line.split() for line in output.splitlines()]
    if len(lines) != samples:
        raise ValueError("missing or extra JSON sample rows")
    timings = {name: [] for name in ("parse", "process", "end_to_end")}
    for index, row in enumerate(lines):
        if len(row) != 8 or row[0] != "JSON_SAMPLE" or int(row[1]) != index:
            raise ValueError(f"invalid JSON sample: {row}")
        checksum = [int(value) for value in row[2:5]]
        if expected is None:
            expected = checksum
        if checksum != expected:
            raise ValueError(f"checksum {checksum} != reference {expected}")
        elapsed = [int(value) for value in row[5:]]
        if any(value < 0 for value in elapsed):
            raise ValueError("negative timing")
        for name, ns in zip(timings, elapsed):
            timings[name].append(ns / 1e9)
    return {"checksum": expected, "timings_s": timings}


def measured(command, env, timeout, directory):
    # GNU time is optional; do not confuse cumulative RUSAGE_CHILDREN with a
    # particular process's peak. RSS includes LLVM children for JIT/build runs.
    timer = Path("/usr/bin/time")
    rss = directory / "peak-rss.txt"
    wrapped = [str(timer), "-f", "%M", "-o", str(rss), *command] if timer.exists() and sys.platform == "linux" else command
    result = execute(wrapped, env, timeout)
    result["peak_rss_kib"] = int(rss.read_text().strip()) if wrapped is not command else None
    result["command"] = command
    return result


def tool_version(tool, env, timeout):
    directory = Path(env.get("PYSTACHY_LLVM", ""))
    command = str(directory / tool) if str(directory) != "." else tool
    try:
        return execute([command, "--version"], env, timeout)["stdout"]
    except (OSError, RuntimeError) as exc:
        return "unavailable: " + str(exc)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"), help="shell-split command; no shell evaluation")
    parser.add_argument("--profiles", nargs="+", choices=PROFILES, default=list(PROFILES))
    parser.add_argument("--modes", nargs="+", choices=("cpython", "jit", "aot"), default=["cpython", "jit", "aot"])
    parser.add_argument("--records", type=positive, default=2000)
    parser.add_argument("--iterations", type=positive, default=5)
    parser.add_argument("--samples", type=positive, default=3)
    parser.add_argument("--processes", type=positive, default=3)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--smoke", action="store_true", help="100 records, one iteration/sample/process; correctness only")
    parser.add_argument("--json", type=Path, default=ROOT / "build/json-benchmark.json")
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("timeout must be positive and finite")
    if args.smoke:
        args.records, args.iterations, args.samples, args.processes = 100, 1, 1, 1
    compiler = shlex.split(args.compiler)
    if not compiler:
        parser.error("empty compiler command")
    if "/" in compiler[0]:
        compiler[0] = str((ROOT / compiler[0]).resolve())
    env = dict(os.environ, PYTHONHASHSEED="0")
    report = {
        "schema_version": 1, "status": "running", "cases": [],
        "scope": "native JSON baseline and source-written guarded control; no compiler specialization",
        "settings": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
        "metadata": {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                     "platform": platform.platform(), "python": sys.version,
                     "cpu_count": os.cpu_count(),
                     "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
                     "load_average": os.getloadavg() if hasattr(os, "getloadavg") else None,
                     "compiler_command": compiler,
                     "compiler_binary_sha256": digest(Path(compiler[0])) if Path(compiler[0]).is_file() else None,
                     "git_revision": execute(["git", "rev-parse", "HEAD"], env, args.timeout)["stdout"].strip(),
                     "git_status": execute(["git", "status", "--porcelain"], env, args.timeout)["stdout"],
                     "source_sha256": {str(path.relative_to(ROOT)): digest(path) for path in
                                       [SOURCE, ROOT / "tools/bench_json.py", ROOT / "runtime.c", ROOT / "runtime.py"] +
                                       sorted((ROOT / "src").rglob("*.py")) + list((ROOT / "lib").glob("json.py"))},
                     "environment": {key: value for key, value in env.items() if key.startswith("PYSTACHY_")}},
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="pystachy-json-bench-") as tmp:
            directory = Path(tmp)
            executable = directory / "json_records"
            if "jit" in args.modes or "aot" in args.modes:
                report["metadata"]["llvm"] = {
                    tool: tool_version(tool, env, args.timeout)
                    for tool in ("clang", "opt", "lli", "llvm-link")
                }
                warm = directory / "startup.py"
                warm.write_text("pass\n")
                report["runtime_cache_prime"] = execute(compiler + ["run", str(warm)], env, args.timeout)
            if "aot" in args.modes:
                report["aot_build"] = measured(compiler + ["build", str(SOURCE), "-o", str(executable)], env, args.timeout, directory)
                report["aot_bytes"] = executable.stat().st_size
            for profile in args.profiles:
                path = directory / f"{profile}.json"
                path.write_text(fixture(args.records, profile), encoding="utf-8")
                runargs = [str(path), "generic", str(args.iterations), str(args.samples)]
                oracle = execute([sys.executable, str(SOURCE), *runargs], env, args.timeout)
                expected = parse_output(oracle["stdout"], args.samples)["checksum"]
                case = {"profile": profile, "input_sha256": digest(path), "input_bytes": path.stat().st_size,
                        "oracle": oracle, "checksum": expected, "runs": [], "summary": {}}
                report["cases"].append(case)
                order = [(mode, algorithm) for mode in args.modes for algorithm in ("generic", "handguarded")]
                for repeat in range(args.processes):
                    rotated = order[repeat % len(order):] + order[:repeat % len(order)]
                    for mode, algorithm in rotated:
                        prefix = {"cpython": [sys.executable, str(SOURCE)], "jit": compiler + ["run", str(SOURCE)],
                                  "aot": [str(executable)]}[mode]
                        runargs[1] = algorithm
                        result = measured(prefix + runargs, env, args.timeout, directory)
                        result.update(parse_output(result["stdout"], args.samples, expected))
                        result.update(mode=mode, algorithm=algorithm, repeat=repeat)
                        case["runs"].append(result)
                for mode, algorithm in order:
                    runs = [run for run in case["runs"] if (run["mode"], run["algorithm"]) == (mode, algorithm)]
                    values = {"wall": summary([run["wall_s"] for run in runs])}
                    for phase in ("parse", "process", "end_to_end"):
                        values[phase] = summary([statistics.median(run["timings_s"][phase]) / args.iterations for run in runs])
                    case["summary"][mode + "/" + algorithm] = values
                    print(profile, mode, algorithm, "checksum", expected, "seconds/document", values)
                if "aot" in args.modes:
                    runargs[1] = "generic"
                    probe = execute([str(executable), *runargs], dict(env, PYSTACHY_GC="stats"), args.timeout)
                    parse_output(probe["stdout"], args.samples, expected)
                    case["aot_gc_probe"] = probe
                    case["aot_gc_probe"]["environment_overrides"] = {"PYSTACHY_GC": "stats"}
            report["status"] = "passed"
    except (OSError, RuntimeError, ValueError) as exc:
        report.update(status="failed", error=str(exc))
        raise
    finally:
        args.json.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
