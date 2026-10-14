"""Reproduce the native stream feedback probe with rotated process-CPU samples."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import statistics
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bench/stream_skew.py"
ORACLE = (
    "from pathlib import Path; import sys; "
    "p=Path(sys.argv[1]); sys.argv=sys.argv[1:]; "
    "code=p.read_text().replace('_stream=stream', 'instream=stream'); "
    "exec(compile(code,str(p),'exec'))"
)


def run(command, env):
    result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                            capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f"{shlex.join(map(str, command))}\n{result.stdout}{result.stderr}")
    return result.stdout.strip()


def rows(path):
    lines = path.read_text().splitlines()
    if not lines or lines[0] != "pystachy-feedback-v1":
        raise RuntimeError(f"Missing feedback header: {path}")
    return [{"site": site, "member": member, "count": int(count)}
            for site, member, count in (line.split("\t") for line in lines[1:])]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=shlex.join([sys.executable, "-m", "pystachy"]))
    parser.add_argument("--repeats", type=int, default=1000)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--timing-cpu", type=int, help="pin timed subprocesses to this allowed CPU")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/benchmarks/stream-feedback.json")
    args = parser.parse_args()
    if args.repeats < 1 or args.samples < 3:
        parser.error("positive repeats and at least three samples are required")
    compiler = shlex.split(args.compiler)
    build = ROOT / "build/stream-feedback"
    build.mkdir(parents=True, exist_ok=True)
    fixture = build / "input.txt"
    profile = build / "training.profile"
    counters = build / "held-out.profile"
    env = dict(os.environ, PYSTACHY_CLOSED_UNIONS="1", PYSTACHY_REFERENCE_UNIONS="1",
               PYSTACHY_FEEDBACK_FUNCTION="tokenize")
    for key in ["PYSTACHY_FEEDBACK_PROFILE", "PYSTACHY_FEEDBACK_RECORD", "PYSTACHY_FEEDBACK_COUNTERS",
                "PYSTACHY_FEEDBACK_OUT", "PYSTACHY_SKEW_PROFILE", "PYSTACHY_GC_STRESS"]:
        env.pop(key, None)
    sources = [SOURCE, ROOT / "lib/shlex.py", ROOT / "lib/io.py", ROOT / "runtime.c",
               ROOT / "runtime.py", Path(__file__).resolve()]
    sources.extend(sorted((ROOT / "src/pystachy_compiler").glob("*.py")))

    def hashes():
        return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sources}

    source_hashes = hashes()
    info = {
        "schema": "pystachy-stream-feedback-v1",
        "platform": platform.platform(), "machine": platform.machine(),
        "python": sys.version, "compiler": compiler,
        "git_head": run(["git", "rev-parse", "HEAD"], env),
        "git_status": run(["git", "status", "--short"], env),
        "repeats": args.repeats, "samples": args.samples,
        "timing_affinity_cpu": args.timing_cpu,
        "timer": "time.process_time inside program; process startup and compilation excluded",
        "training": "controlled 199 StringIO calls and 1 TextIO call; not natural application skew",
        "builds": {}, "checks": {}, "timings": {},
    }
    llvm = env.get("PYSTACHY_LLVM", "")
    if llvm:
        info["llvm"] = run([str(Path(llvm) / "clang"), "--version"], env).splitlines()[0]
    expected = run([sys.executable, "-c", ORACLE, str(SOURCE), "check", "1", str(fixture)], env)
    info["checks"]["upstream_cpython"] = expected

    def compile_variant(name, options):
        target = build / name
        start = time.perf_counter()
        run([*compiler, "build", str(SOURCE), "-o", str(target)], dict(env, **options))
        info["builds"][name] = {"wall_seconds": time.perf_counter() - start,
                                "executable_bytes": target.stat().st_size,
                                "compile_options": options}
        actual = run([str(target), "check", "1", str(fixture)], env)
        if actual != expected:
            raise RuntimeError(f"{name} differs from upstream CPython: {actual!r} != {expected!r}")
        info["checks"][name] = actual
        return target

    baseline = compile_variant("baseline", {})
    record = compile_variant("record", {"PYSTACHY_FEEDBACK_RECORD": "1"})
    training = run([str(record), "train", "1", str(fixture)],
                   dict(env, PYSTACHY_FEEDBACK_OUT=str(profile)))
    info["checks"]["training"] = training
    info["profile"] = rows(profile)
    observed = {row["member"]: row["count"] for row in info["profile"]}
    if sorted(observed.values()) != [1, 199]:
        raise RuntimeError(f"Unexpected training counts: {observed}")
    selected = {"PYSTACHY_FEEDBACK_PROFILE": str(profile)}
    optimized = compile_variant("optimized", selected)
    counted = compile_variant("counters", dict(selected, PYSTACHY_FEEDBACK_COUNTERS="1"))
    actual = run([str(counted), "check", "1", str(fixture)],
                 dict(env, PYSTACHY_FEEDBACK_OUT=str(counters)))
    if actual != expected:
        raise RuntimeError("Instrumented check differs")
    info["counters"] = rows(counters)
    counts = {row["member"]: row["count"] for row in info["counters"]}
    if counts != {"<hot>": 7, "<miss>": 17}:
        raise RuntimeError(f"Unexpected held-out counters: {counts}")
    for name, options in [("jit_baseline", {}), ("jit_optimized", selected)]:
        actual = run([*compiler, "run", str(SOURCE), "check", "1", str(fixture)], dict(env, **options))
        if actual != expected:
            raise RuntimeError(f"{name} differs from upstream CPython")
        info["checks"][name] = actual

    # Keep counters and recording out of timing builds. Rotate variants each round.
    variants = [("generic", baseline, "bench"), ("selected", optimized, "bench"),
                ("concrete", baseline, "static")]
    samples = {name: [] for name, _, _ in variants}
    original_affinity = None
    if args.timing_cpu is not None:
        original_affinity = os.sched_getaffinity(0)
        if args.timing_cpu not in original_affinity:
            raise RuntimeError(f"CPU {args.timing_cpu} is not in the allowed affinity set")
        os.sched_setaffinity(0, {args.timing_cpu})
    for round_number in range(args.samples):
        ordered = variants[round_number % len(variants):] + variants[:round_number % len(variants)]
        for name, executable, mode in ordered:
            output = run([str(executable), mode, str(args.repeats), str(fixture)], env)
            checksum, elapsed = output.split()
            if int(checksum) != 586964006 * args.repeats:
                raise RuntimeError(f"Timed checksum differs: {output}")
            samples[name].append(float(elapsed))
    if original_affinity is not None:
        os.sched_setaffinity(0, original_affinity)
    for name, values in samples.items():
        info["timings"][name] = {"process_cpu_seconds": values, "median": statistics.median(values),
                                 "min": min(values), "max": max(values)}
    info["ratios"] = {
        "generic_over_selected": info["timings"]["generic"]["median"] / info["timings"]["selected"]["median"],
        "generic_over_concrete": info["timings"]["generic"]["median"] / info["timings"]["concrete"]["median"],
    }
    info["paired_ratios"] = {}
    for key, target in [("generic_over_selected", "selected"), ("generic_over_concrete", "concrete")]:
        values = [samples["generic"][i] / samples[target][i] for i in range(args.samples)]
        info["paired_ratios"][key] = {"values": values, "median": statistics.median(values),
                                      "min": min(values), "max": max(values)}
    if hashes() != source_hashes:
        raise RuntimeError("Compiler, runtime or workload source changed during measurement; rerun")
    info["source_sha256"] = source_hashes
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "timings": info["timings"],
                      "ratios": info["ratios"], "profile": info["profile"],
                      "counters": info["counters"]}, indent=2))


if __name__ == "__main__":
    main()
