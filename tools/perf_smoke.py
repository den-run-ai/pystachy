"""Small advisory base/head comparison; no dependencies or historical timing gate."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import tempfile

from bench_extended import execute
from bench_pyperformance import BENCHMARKS, run

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "autograd": ("bench/smoke/ml.py", ["autograd", "40000"]),
    "numeric": ("bench/smoke/ml.py", ["numeric", "20000"]),
    "fnmatch": ("bench/smoke/text.py", ["fnmatch", "1000"]),
    "json": ("bench/smoke/text.py", ["json", "6000"]),
    "repair_scan": ("bench/smoke/text.py", ["repair_scan", "400"]),
    "copy_int": ("bench/smoke/identity.py", ["int", "6000000", "123"]),
    "copy_float": ("bench/smoke/identity.py", ["float", "6000000", "123"]),
    "global_int": ("bench/smoke/identity.py", ["global_int", "6000000", "123"]),
    "global_float": ("bench/smoke/identity.py", ["global_float", "6000000", "123"]),
    "graph_copy": ("tools/dynany_bench.py", ["graph-smoke", "4000"]),
    "regex_effbot": ("bench/pyperformance/regex_effbot.py", BENCHMARKS["regex_effbot"][0]),
}
METRICS = ("build_s", "jit_process_s", "jit_loop_s", "aot_process_s", "aot_loop_s")


def compare(base, head):
    if len(base) != 3 or len(head) != 3 or any(
        not math.isfinite(x) or x <= 0 for x in base + head
    ):
        raise ValueError("expected three finite, positive samples per revision")
    b, h = statistics.median(base), statistics.median(head)
    return {"base_s": b, "head_s": h, "ratio": h / b,
            "candidate": (h / b >= 1.20 or math.isclose(h / b, 1.20))
            and (h - b >= 0.005 or math.isclose(h - b, 0.005)),
            "separated": min(head) > max(base)}


def classify(first, confirmation):
    if not first["candidate"]:
        return "ok"
    if confirmation and confirmation["candidate"] and first["separated"] and confirmation["separated"]:
        return "warning"
    return "unconfirmed"


def batch(source, arguments, compilers, envs, directory, expected, offset=0, measure_build=True):
    metrics = METRICS if measure_build else METRICS[1:]
    samples = {side: {metric: [] for metric in metrics} for side in compilers}
    samples["cpython"] = []
    for repeat in range(3):
        # Interleave both revisions and CPython; rotate which revision runs first.
        samples["cpython"].append(run([sys.executable, str(source), *arguments],
                                      envs["head"], 60, expected))
        for side in (("base", "head") if (repeat + offset) % 2 == 0 else ("head", "base")):
            compiler, env = compilers[side], envs[side]
            exe = str(directory / side / source.stem)
            if measure_build:
                build = execute([compiler, "build", str(source), "-o", exe], env, 60)
                samples[side]["build_s"].append(build["wall_s"])
            jit = run([compiler, "run", str(source), *arguments], env, 60, expected)
            aot = run([exe, *arguments], env, 60, expected)
            values = (jit["wall_s"], jit["loop_s"], aot["wall_s"], aot["loop_s"])
            for metric, value in zip(METRICS[1:], values):
                samples[side][metric].append(value)
    return samples


def measure(name, compilers, envs, directory, built):
    path, arguments = CASES[name]
    source = ROOT / path
    measure_build = path not in built
    oracle = run([sys.executable, str(source), *arguments], envs["head"], 60)
    # Warm compilation caches and check both modes before collecting any samples.
    for side, compiler in compilers.items():
        exe = str(directory / side / source.stem)
        if measure_build:
            execute([compiler, "build", str(source), "-o", exe], envs[side], 60)
        run([compiler, "run", str(source), *arguments], envs[side], 60, oracle["stdout"])
        run([exe, *arguments], envs[side], 60, oracle["stdout"])
    first = batch(source, arguments, compilers, envs, directory, oracle["stdout"], measure_build=measure_build)
    comparisons = {metric: compare(first["base"][metric], first["head"][metric]) for metric in first["base"]}
    confirmation = (batch(source, arguments, compilers, envs, directory, oracle["stdout"], 3, measure_build)
                    if any(c["candidate"] for c in comparisons.values()) else None)
    for metric, result in comparisons.items():
        second = compare(confirmation["base"][metric], confirmation["head"][metric]) if confirmation else None
        result.update(status=classify(result, second), confirmation=second)
    built.add(path)
    return {"name": name, "source": path, "arguments": arguments, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "loop_clock": "process_time_ns" if name == "graph_copy" else "perf_counter",
            "output": oracle["stdout"], "samples": first, "confirmation": confirmation, "comparison": comparisons}


def summary(report):
    lines = ["## Performance smoke (advisory)", "",
             f"Base `{report['revisions']['base']}` → head `{report['revisions']['head']}`.", "",
             "Three pairs; ≥20% and ≥5 ms slower triggers three confirmation pairs. Warnings require",
             "both batches to meet the threshold with non-overlapping base/head ranges.", "",
             "Build time is measured once per source file, shown on its first workload.", "",
             "graph_copy loop time measures processing CPU seconds; other loop times measure wall seconds.", "",
             "| Workload | Metric | Base | Head | Change | Result |",
             "|---|---|---:|---:|---:|---|"]
    for result in report["results"]:
        for metric, c in result["comparison"].items():
            lines.append(f"| {result['name']} | {metric} | {c['base_s']:.4f}s | {c['head_s']:.4f}s | "
                         f"{(c['ratio'] - 1) * 100:+.1f}% | {c['status']} |")
            if c["status"] == "warning":
                print(f"::warning::{result['name']} {metric}: confirmed >=20% slowdown; see performance artifact")
    return "\n".join(lines) + "\n"


def write_report(path, report):
    """Publish a valid checkpoint; cancellation must not truncate the previous one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(report, output, indent=2)
            output.write("\n")
            output.flush()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True, help="baseline checkout")
    parser.add_argument("--json", type=Path, default=Path("build/perf-smoke.json"))
    args = parser.parse_args()
    # Preserve toolchain discovery, but prevent inherited GC/optimization/import settings.
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_") and k != "PYTHONPATH"}
    if "PYSTACHY_LLVM" in os.environ:
        env["PYSTACHY_LLVM"] = os.environ["PYSTACHY_LLVM"]
    env["PYTHONHASHSEED"] = "0"
    affinity = None
    report = {"schema": 2, "status": "incomplete", "phase": "setup",
              "revisions": {}, "bootstrap": {}, "results": []}
    try:
        write_report(args.json, report)
        affinity = sorted(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {affinity[0]})
        roots = {"base": args.base.resolve(), "head": ROOT}
        report.update(python=sys.version, platform=platform.platform(),
                      runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      cpu=Path("/proc/cpuinfo").read_text().split("model name", 1)[-1].splitlines()[0],
                      affinity=[affinity[0]], load_average=os.getloadavg())
        write_report(args.json, report)
        with tempfile.TemporaryDirectory(prefix="pystachy-perf-") as tmp:
            directory = Path(tmp)
            compilers, envs = {}, {}
            for side, root in roots.items():
                report["phase"] = f"bootstrap:{side}"
                write_report(args.json, report)
                report["revisions"][side] = execute(["git", "-C", str(root), "rev-parse", "HEAD"], env, 10)["stdout"].strip()
                (directory / side).mkdir()
                envs[side] = dict(env, PYSTACHY_HOME=str(root), PYSTACHY_CACHE=str(directory / side / "cache"))
                compiler = str(directory / side / "compiler")
                print(f"Building {side} compiler at {report['revisions'][side]}", flush=True)
                write_report(args.json, report)
                report["bootstrap"][side] = execute([sys.executable, str(root / "pystachy.py"), "build",
                                                     str(root / "pystachy.py"), "-o", compiler], envs[side], 180)
                compilers[side] = compiler
                write_report(args.json, report)
            report["phase"] = "toolchain"
            write_report(args.json, report)
            llvm = Path(env.get("PYSTACHY_LLVM", "/usr/lib/llvm-18/bin"))
            report["clang"] = execute([str(llvm / "clang"), "--version"], env, 10)["stdout"]
            built = set()
            for name in CASES:
                report["phase"] = f"measure:{name}"
                write_report(args.json, report)
                print(f"Measuring {name}", flush=True)
                report["results"].append(measure(name, compilers, envs, directory, built))
                write_report(args.json, report)
        report["phase"] = "summary"
        write_report(args.json, report)
        text = summary(report)
        print(text)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as output:
                output.write(text)
        report.update(status="complete", phase="complete")
    except BaseException as exc:
        report["status"] = "error"
        report["error"] = str(exc)
        report["error_type"] = type(exc).__name__
        raise
    finally:
        try:
            write_report(args.json, report)
        finally:
            if affinity is not None:
                os.sched_setaffinity(0, affinity)


if __name__ == "__main__":
    main()
