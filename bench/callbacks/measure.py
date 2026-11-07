"""Compare generic and precompiled guarded callbacks on Linux, alternating run order on a pinned CPU."""
import argparse
import json
import os
from pathlib import Path
import hashlib
import platform
from statistics import median
import subprocess
import sys
import tempfile
import time


HERE = Path(__file__).resolve().parent
NAMES = ("generic", "guarded")
MODES = ("hit", "skew", "mixed", "miss", "change")


def run(argv, env):
    # wait4 includes the largest waited-for compiler child. A small AOT app
    # instead reads its own high-water mark, avoiding the Python launcher's RSS.
    with tempfile.TemporaryFile() as output:
        start = time.perf_counter()
        with subprocess.Popen(argv, env=env, stdout=output) as process:
            _, status, usage = os.wait4(process.pid, 0)
            process.returncode = os.waitstatus_to_exitcode(status)
            elapsed = time.perf_counter() - start
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, argv)
        output.seek(0)
        return {"wall": elapsed, "rss_kib": usage.ru_maxrss, "output": output.read().decode().splitlines()}


def fixture(work, filename, target, source_guard):
    text = (HERE / filename).read_text()
    if source_guard:
        original = "    return search(key)\n"
        if text.count(original) != 1:
            raise ValueError("source control requires exactly one return search(key)")
        guard = f"    if key is {target}:\n        return search({target})\n"
        text = text.replace(original, guard + original)
    program = work / filename
    program.write_text(text)
    return program


def check(actual, expected, case):
    if actual != expected:
        raise ValueError(f"{case}: expected {expected!r}, got {actual!r}")


def checksum(mode, count):
    # Sum insertion positions directly from the sorted field lengths, independently
    # of the callback and bisect implementations. Each miss cycles over three offsets.
    hits = [sum(max((i * 569) % 1025 - offset, 0) for i in range(509)) for offset in (0, 11, 5, 17)]

    def cycle(values, length):
        repetitions, tail = divmod(length, len(values))
        return repetitions * sum(values) + sum(values[:tail])

    if mode == "hit":
        return count * hits[0]
    if mode == "mixed":
        return cycle(hits, count)
    if mode == "miss":
        return cycle(hits[1:], count)
    if mode == "skew":
        misses = count // 10
        return (count - misses) * hits[0] + cycle(hits[1:], misses)
    if mode == "change":
        start, end = count // 3, 2 * count // 3
        return (count - end + start) * hits[0] + cycle(hits[1:], end) - cycle(hits[1:], start)
    raise ValueError(f"unknown profile {mode!r}")


def validate(program, app, compiler, args, env):
    expected = run([sys.executable, HERE / program.name, *args], env)["output"]
    run([*compiler, "build", program, "-o", app], env)
    for stress in ("0", "1"):
        jit = run([*compiler, "run", program, *args], {**env, "PYSTACHY_GC_STRESS_PROGRAM": stress})
        check(jit["output"], expected, (program.name, "JIT", stress))
        aot = run([app, *args], {**env, "PYSTACHY_GC_STRESS": stress})
        check(aot["output"], expected, (program.name, "AOT", stress))
    return expected


def time_app(command, mode, count, env):
    result = run([*command, mode, str(count)], env)
    value, elapsed = result.pop("output")
    check(int(value), checksum(mode, count), (mode, count, command))
    result.update(count=count, checksum=value, kernel=float(elapsed))
    return result


def summarize(samples, profile, key, count=None):
    groups = [[row[key] for row in samples if row["variant"] == name and row["profile"] == profile
               and row.get("count") == count] for name in NAMES]
    base, guard = groups
    pairs = [a / b for a, b in zip(base, guard, strict=True)]
    print(f"{profile:10} {str('' if count is None else count):7} {key:7}  {median(base):.5f} -> {median(guard):.5f} s"
          f"  {median(pairs):.3f}x paired [{min(pairs):.3f}, {max(pairs):.3f}]")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="new output directory for raw samples, binaries and IR")
    parser.add_argument("--source-compiler", type=Path,
                        help="use this native compiler with a hand-written source guard as the control")
    parser.add_argument("--rounds", type=int, default=7)
    parser.add_argument("--batches", type=int, default=15000)
    parser.add_argument("--long-batches", type=int, default=150000)
    args = parser.parse_args()
    pinned = (HERE.parents[1] / ".python-version").read_text().strip()
    if sys.platform != "linux" or sys.implementation.name != "cpython" or platform.python_version() != pinned:
        parser.error(f"this benchmark requires Linux and CPython {pinned}")
    if min(args.rounds, args.batches, args.long_batches) < 1:
        parser.error("rounds and batch sizes must be positive")
    cpus = sorted(os.sched_getaffinity(0))
    if args.rounds > 1 and len(cpus) != 1:
        parser.error("pin the benchmark to one available CPU with taskset -c CPU")
    root = args.results.resolve()
    root.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_") or k == "PYSTACHY_LLVM"}
    env["PYSTACHY_CACHE"] = str(root / "runtime-cache")
    files = [HERE / name for name in ("callback_bisect.py", "callback_effects.py", "variant.py", "measure.py")]
    if args.source_compiler:
        files.append(args.source_compiler.resolve())
    metadata = {
        "comparison": "source" if args.source_compiler else "descriptor",
        "cpython": pinned, "platform": platform.platform(), "cpu_affinity": cpus,
        "rounds": args.rounds, "batches": args.batches, "long_batches": args.long_batches,
        "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
    }
    (root / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    samples = []
    compilers = {}
    for name in NAMES:
        compiler = ([args.source_compiler.resolve()] if args.source_compiler else
                    [sys.executable, HERE / "variant.py", name])
        compilers[name] = compiler
        work = root / name
        work.mkdir()
        source_guard = args.source_compiler is not None and name == "guarded"
        effects = fixture(work, "callback_effects.py", "project", source_guard)
        validate(effects, work / "effects", compiler, [], env)
        program = fixture(work, "callback_bisect.py", "text_length", source_guard)
        app = work / "app"
        check(validate(program, app, compiler, ["check"], env), ["positions 2545"], "position oracle")
        for mode in MODES:
            ref = run([sys.executable, HERE / program.name, mode, "30"], env)["output"][0]
            check(int(ref), checksum(mode, 30), ("CPython", mode))
            time_app([*compiler, "run", program], mode, 30, env)
            time_app([app], mode, 30, env)
        value, _, rss = run([app, "skew", str(args.batches), "memory"], env)["output"]
        check(int(value), checksum("skew", args.batches), "memory run")
        samples.append(dict(variant=name, profile="app-memory", rss_kib=int(rss)))
        with (work / "module.ll").open("w") as ir:
            subprocess.run([*compiler, "ir", program], env=env, stdout=ir, check=True)

    profiles = list(dict.fromkeys([("hit", 0), ("hit", 1), *((mode, args.batches) for mode in MODES)]))
    for rep in range(args.rounds):
        order = NAMES if rep % 2 == 0 else NAMES[::-1]
        for name in order:
            work = root / name
            app = work / "app"
            build = run([*compilers[name], "build", work / "callback_bisect.py", "-o", app], env)
            build.pop("output")
            samples.append(dict(build, rep=rep, variant=name, profile="build", bytes=app.stat().st_size))
        for count in (0, args.batches):
            for name in order:
                result = time_app([*compilers[name], "run", root / name / "callback_bisect.py"], "skew", count, env)
                samples.append(dict(result, rep=rep, variant=name, profile="jit-skew"))
        for mode, count in profiles:
            for name in order:
                result = time_app([root / name / "app"], mode, count, env)
                result.pop("rss_kib")
                samples.append(dict(result, rep=rep, variant=name, profile=mode))
        (root / "samples.json").write_text(json.dumps(samples, indent=2) + "\n")
        print(f"completed round {rep + 1}/{args.rounds}", flush=True)

    # Include compilation and the first launch in one directly timed measurement.
    long_samples = []
    long_checksum = checksum("skew", args.long_batches)
    for rep in range(args.rounds):
        for name in (NAMES if rep % 2 == 0 else NAMES[::-1]):
            work = root / name
            start = time.perf_counter()
            build = run([*compilers[name], "build", work / "callback_bisect.py", "-o", work / "app"], env)
            app = run([work / "app", "skew", str(args.long_batches)], env)
            total = time.perf_counter() - start
            value, kernel = app["output"]
            check(int(value), long_checksum, "build and first launch")
            long_samples.append(dict(rep=rep, variant=name, profile="long", count=args.long_batches, wall=total,
                                     build=build["wall"], app=app["wall"], kernel=float(kernel), checksum=value))
        (root / "long.json").write_text(json.dumps(long_samples, indent=2) + "\n")
        print(f"completed long round {rep + 1}/{args.rounds}", flush=True)

    summarize(samples, "build", "wall")
    summarize(samples, "jit-skew", "wall", 0)
    summarize(samples, "jit-skew", "wall", args.batches)
    for mode, count in profiles:
        summarize(samples, mode, "wall", count)
    summarize(long_samples, "long", "wall", args.long_batches)
    summarize(long_samples, "long", "kernel", args.long_batches)


if __name__ == "__main__":
    main()
