"""Small advisory base/head comparison; no dependencies or historical timing gate.

The default suite times eleven small workloads in JIT and AOT on every push and PR. The weekly
suite (scheduled and manual runs only) times every adapted pyperformance port and bench/*.py
microbenchmark in AOT, which the eleven missed when words and float slowed down (#1302).
"""
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
import time

from bench_extended import execute
from bench_pyperformance import BENCHMARKS, port_path, run

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
# The weekly suite flags a confirmed slowdown of 10% and 2 ms: a smaller one than the default suite's
# 20% and 5 ms, which its many more, longer AOT workloads and one metric each can resolve.
WEEKLY_RATIO = 1.10
WEEKLY_FLOOR = 0.002
WEEKLY_TIMEOUT = 300  # (seconds for one build or run: regex ports import lib/re)


class BudgetExhausted(Exception):
    """The suite's deadline, rather than a revision's command limit, stopped work."""


def budgeted(function, command, env, timeout, *args, deadline=None):
    """Bound every command, including bootstraps, by the suite's remaining time."""
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BudgetExhausted("out of the time budget")
        limit = min(timeout, remaining)
    else:
        limit = timeout
    try:
        return function(command, env, limit, *args)
    except RuntimeError as error:
        if limit < timeout and str(error).startswith("timeout after "):
            raise BudgetExhausted("out of the time budget") from error
        raise


def compare(base, head, ratio=1.20, floor=0.005):
    if len(base) != 3 or len(head) != 3 or any(
        not math.isfinite(x) or x <= 0 for x in base + head
    ):
        raise ValueError("expected three finite, positive samples per revision")
    b, h = statistics.median(base), statistics.median(head)
    return {"base_s": b, "head_s": h, "ratio": h / b,
            "candidate": (h / b >= ratio or math.isclose(h / b, ratio))
            and (h - b >= floor or math.isclose(h - b, floor)),
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


def weekly_cases(head):
    """The weekly suite's workloads in head: (source, arguments, metric) by name. Each pyperformance
    port runs its measured arguments, timed by its 'seconds' line (aot_loop_s); each bench/*.py
    microbenchmark runs as bench/run.sh runs it, timed as a process (aot_process_s)."""
    cases = {}
    for name, (arguments, _) in BENCHMARKS.items():
        cases["pyperformance/" + name] = (str(port_path(name).relative_to(ROOT)), list(arguments), "aot_loop_s")
    for source in sorted((head / "bench").glob("*.py")):
        cases["bench/" + source.stem] = (f"bench/{source.name}", [], "aot_process_s")
    return cases


def first_line(error):
    text = str(error).strip()
    return text.splitlines()[0][:300] if text else type(error).__name__


def aot_sample(exe, arguments, env, expected, metric, deadline=None):
    """One AOT run's seconds of metric; its stdout must be CPython's."""
    if metric == "aot_loop_s":
        seconds = budgeted(run, [exe, *arguments], env, WEEKLY_TIMEOUT, expected, deadline=deadline)["loop_s"]
    else:
        record = budgeted(execute, [exe, *arguments], env, WEEKLY_TIMEOUT, deadline=deadline)
        if record["stdout"] != expected:
            raise ValueError(f"output differs from CPython's: {exe}\nexpected: {expected[-500:]!r}\n"
                             f"got: {record['stdout'][-500:]!r}")
        seconds = record["wall_s"]
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError(f"invalid elapsed time: {exe}: {seconds}")
    return seconds


def weekly_batch(exes, arguments, envs, expected, metric, samples, failures, offset=0, deadline=None):
    """Retain partial pairs and check the other revision even when one fails."""
    for repeat in range(3):
        for side in (("base", "head") if (repeat + offset) % 2 == 0 else ("head", "base")):
            if side in failures:
                continue
            try:
                samples[side].append(aot_sample(exes[side], arguments, envs[side], expected, metric, deadline))
            except (OSError, RuntimeError, ValueError) as error:
                phase = "confirmation" if offset else "sample"
                failures[side] = {"phase": f"{phase}:{repeat + 1}", "error": str(error)[-2000:]}


def measure_weekly(name, case, compilers, envs, directory, head, deadline=None):
    """A weekly workload's AOT comparison. A base that cannot build it or print CPython's output
    skips it, as a compiler older than the workload may; the head's failure is an error."""
    path, arguments, metric = case
    source = head / path
    result = {"name": name, "source": path, "arguments": arguments, "metric": metric}
    if not source.is_file():
        return dict(result, status="skipped", reason="not in the head revision")
    result["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    failures = result["failures"] = {}
    first = result["samples"] = {"base": [], "head": []}
    result["confirmation"] = None
    try:
        oracle = budgeted(execute, [sys.executable, str(source), *arguments], envs["head"],
                          WEEKLY_TIMEOUT, deadline=deadline)
        result["output_sha256"] = hashlib.sha256(oracle["stdout"].encode()).hexdigest()
        exes = {}
        # Both builds, then warmups: building between warmups biased the first timed sample.
        for step in ("build", "warmup"):
            for side in ("base", "head"):
                if side in failures:
                    continue
                exe = directory / side / ("weekly-" + name.replace("/", "-"))
                try:
                    if step == "build":
                        build = budgeted(execute, [compilers[side], "build", str(source), "-o", str(exe)],
                                         envs[side], WEEKLY_TIMEOUT, deadline=deadline)
                        result[side + "_build_s"] = build["wall_s"]
                        exes[side] = str(exe)
                    else:
                        aot_sample(str(exe), arguments, envs[side], oracle["stdout"], metric, deadline)
                except (OSError, RuntimeError, ValueError) as error:
                    failures[side] = {"phase": step, "error": str(error)[-2000:]}
        weekly_batch(exes, arguments, envs, oracle["stdout"], metric, first, failures, deadline=deadline)
        if not failures and compare(first["base"], first["head"], WEEKLY_RATIO, WEEKLY_FLOOR)["candidate"]:
            result["confirmation"] = {"base": [], "head": []}
            weekly_batch(exes, arguments, envs, oracle["stdout"], metric, result["confirmation"], failures,
                         3, deadline=deadline)
    except BudgetExhausted:
        result["budget_exhausted"] = True
    if "head" in failures:
        return dict(result, status="error", error=failures["head"]["error"])
    if "base" in failures:
        return dict(result, status="skipped", reason=f"the base fails it: {first_line(failures['base']['error'])}")
    if result.get("budget_exhausted"):
        return dict(result, status="skipped", reason="out of the time budget")
    comparison = compare(first["base"], first["head"], WEEKLY_RATIO, WEEKLY_FLOOR)
    confirmation = result["confirmation"]
    second = (compare(confirmation["base"], confirmation["head"], WEEKLY_RATIO, WEEKLY_FLOOR)
              if confirmation else None)
    comparison.update(status=classify(comparison, second), confirmation=second)
    return dict(result, status=comparison["status"], comparison={metric: comparison})


def weekly_summary(report):
    lines = ["## Weekly AOT performance (advisory)", "",
             f"Base `{report['revisions']['base']}` → head `{report['revisions']['head']}`.", "",
             "Every adapted pyperformance port (its timed part) and bench/*.py microbenchmark (the process),",
             "in AOT, with CPython's output: three alternating pairs; ≥10% and ≥2 ms slower triggers three",
             "confirmation pairs. Warnings require both batches to meet the threshold with non-overlapping",
             "base/head ranges.", "",
             "| Workload | Metric | Base | Head | Change | Result |",
             "|---|---|---:|---:|---:|---|"]
    notes = []
    for result in report["results"]:
        if "comparison" not in result:
            notes.append(f"- {result['name']}: {result['status']}, {result.get('reason') or first_line(result.get('error', ''))}")
            continue
        for metric, c in result["comparison"].items():
            lines.append(f"| {result['name']} | {metric} | {c['base_s'] * 1000:.2f} ms | {c['head_s'] * 1000:.2f} ms | "
                         f"{(c['ratio'] - 1) * 100:+.1f}% | {c['status']} |")
            if c["status"] == "warning":
                print(f"::warning::{result['name']} {metric}: confirmed >=10% slowdown; see performance artifact")
    return "\n".join(lines + ([""] + notes if notes else [])) + "\n"


def summary(report):
    lines = ["## Performance smoke (advisory)", "",
             f"Base `{report['revisions']['base']}` → head `{report['revisions']['head']}`.", "",
             "Three pairs; ≥20% and ≥5 ms slower triggers three confirmation pairs. Warnings require",
             "both batches to meet the threshold with non-overlapping base/head ranges.", "",
             "Build time is measured once per source file, shown on its first workload.", "",
             "JIT process measurements include frontend and LLVM work; program caching is disabled.", "",
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
    parser.add_argument("--suite", choices=("smoke", "weekly"), default="smoke",
                        help="smoke: eleven workloads in JIT and AOT; weekly: every pyperformance port and "
                             "bench/*.py microbenchmark in AOT")
    parser.add_argument("--head", type=Path, default=ROOT,
                        help="head checkout, whose compiler and workloads --suite weekly measures (default: this one)")
    parser.add_argument("--only", default="", help="comma-separated workloads of the suite (default: all of them)")
    parser.add_argument("--budget", type=float, default=0,
                        help="--suite weekly: maximum seconds for builds and runs, including commands in flight (default: none)")
    args = parser.parse_args()
    started = time.monotonic()
    head = args.head.resolve()
    if args.suite == "smoke" and (head != ROOT or args.budget):
        parser.error("--head and --budget need --suite weekly")
    if not math.isfinite(args.budget) or args.budget < 0:
        parser.error("--budget must be finite and nonnegative")
    deadline = started + args.budget if args.budget else None
    cases = CASES if args.suite == "smoke" else weekly_cases(head)
    names = [name for name in args.only.split(",") if name] or list(cases)
    unknown = [name for name in names if name not in cases]
    if unknown:
        parser.error(f"not a workload of the {args.suite} suite: {', '.join(unknown)}")
    # Preserve toolchain discovery, but prevent inherited GC/optimization/import settings.
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_") and k != "PYTHONPATH"}
    if "PYSTACHY_LLVM" in os.environ:
        env["PYSTACHY_LLVM"] = os.environ["PYSTACHY_LLVM"]
    env["PYSTACHY_PROGRAM_CACHE"] = "0"
    env["PYTHONHASHSEED"] = "0"
    affinity = None
    report = {"schema": 2, "suite": args.suite, "status": "incomplete", "phase": "setup",
              "revisions": {}, "bootstrap": {}, "results": [],
              "environment": {"PYSTACHY_PROGRAM_CACHE": env["PYSTACHY_PROGRAM_CACHE"]}}
    if args.suite == "weekly":
        report["thresholds"] = {"ratio": WEEKLY_RATIO, "floor_s": WEEKLY_FLOOR}
    try:
        write_report(args.json, report)
        affinity = sorted(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {affinity[0]})
        roots = {"base": args.base.resolve(), "head": head}
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
                report["revisions"][side] = budgeted(execute, ["git", "-C", str(root), "rev-parse", "HEAD"],
                                                      env, 10, deadline=deadline)["stdout"].strip()
                (directory / side).mkdir()
                envs[side] = dict(env, PYSTACHY_HOME=str(root), PYSTACHY_CACHE=str(directory / side / "cache"))
                compiler = str(directory / side / "compiler")
                print(f"Building {side} compiler at {report['revisions'][side]}", flush=True)
                write_report(args.json, report)
                report["bootstrap"][side] = budgeted(execute, [sys.executable, str(root / "pystachy.py"), "build",
                                                              str(root / "pystachy.py"), "-o", compiler],
                                                     envs[side], 180, deadline=deadline)
                compilers[side] = compiler
                write_report(args.json, report)
            report["phase"] = "toolchain"
            write_report(args.json, report)
            llvm = Path(env.get("PYSTACHY_LLVM", "/usr/lib/llvm-18/bin"))
            report["clang"] = budgeted(execute, [str(llvm / "clang"), "--version"], env, 10,
                                       deadline=deadline)["stdout"]
            built = set()
            for name in names:
                if deadline is not None and time.monotonic() >= deadline:
                    report["results"].append({"name": name, "status": "skipped", "reason": "out of the time budget",
                                              "budget_exhausted": True})
                    continue
                report["phase"] = f"measure:{name}"
                write_report(args.json, report)
                print(f"Measuring {name}", flush=True)
                report["results"].append(measure(name, compilers, envs, directory, built) if args.suite == "smoke"
                                         else measure_weekly(name, cases[name], compilers, envs, directory, head, deadline))
                write_report(args.json, report)
        report["phase"] = "summary"
        write_report(args.json, report)
        text = summary(report) if args.suite == "smoke" else weekly_summary(report)
        print(text)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as output:
                output.write(text)
        failed = [result["name"] for result in report["results"] if result.get("status") == "error"]
        if failed:
            raise RuntimeError(f"the head revision fails {len(failed)} workloads: {', '.join(failed)}")
        exhausted = any(result.get("budget_exhausted") for result in report["results"])
        report.update(status="incomplete" if exhausted else "complete", phase="complete")
    except BudgetExhausted as exc:
        report.update(status="incomplete", budget_exhausted=True, reason=str(exc))
        measured = {result["name"] for result in report["results"]}
        report["results"].extend({"name": name, "status": "skipped", "reason": str(exc), "budget_exhausted": True}
                                 for name in names if name not in measured)
        print(f"Weekly performance stopped during {report['phase']}: {exc}; see the partial report.")
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
