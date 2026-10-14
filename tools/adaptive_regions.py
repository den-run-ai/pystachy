"""Profile three CPython workloads, then compare a selected native call region.

This is a feasibility experiment on small application fragments, not an estimate
of compatibility across arbitrary installed Python applications. Timing samples
run without profiling hooks; every result is checked against unchanged CPython.
"""

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shlex
import sys
import tempfile
import time
import uuid

import adaptive
from adaptive_bench import positive, summary
from bench_extended import execute


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples" / "adaptive"))
import workloads  # noqa: E402 - the standalone controller locates its example module.


@contextmanager
def compiler_cache(directory):
    previous = os.environ.get("PYSTACHY_CACHE")
    os.environ["PYSTACHY_CACHE"] = str(directory)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("PYSTACHY_CACHE", None)
        else:
            os.environ["PYSTACHY_CACHE"] = previous


def checked_run(function, phase, batches, inner, expected=None):
    if sys.getprofile() is not None or sys.gettrace() is not None:
        raise RuntimeError("application timings require profiling and tracing disabled")
    if expected is None:
        expected = workloads.run_numeric(phase, batches, inner=inner)
    start = time.perf_counter()
    actual = function(phase, batches, inner=inner)
    elapsed = time.perf_counter() - start
    # Records carry exact scalar types as well as values, including huge ints.
    if actual != expected:
        raise RuntimeError(f"{phase} application output differs from CPython")
    return elapsed


def application(wrapper, boundary):
    option = "step" if boundary == "leaf" else "batch"

    def run(phase, batches, *, inner):
        return workloads.run_numeric(phase, batches, inner=inner, **{option: wrapper})

    return run


def compile_static_region(compiler, directory):
    """Supply known types before seeing inputs, using the same compiler and ABI."""
    graph = adaptive._Region(workloads.numeric_batch, {"numeric_step": workloads.numeric_step})
    variants, sources, sizes = {}, {}, {}
    for kind in (int, float):
        key = f"{kind.__name__},int"
        source = graph.source((kind, int), kind)
        name = "_static_region_" + uuid.uuid4().hex
        variants[kind] = adaptive._compile_variant(source, compiler, directory, name)
        sources[key] = source
        sizes[key] = (directory / f"{name}.abi3.so").stat().st_size

    counts = {"native_calls": 0, "fallback_calls": 0, "overflow_replays": 0}

    def static_entry(x, n):
        # The application still supplies Python values. Retain boundary guards
        # for held-out inputs; there is no profiling, learning or compile path.
        if ((type(x) is not int and type(x) is not float) or type(n) is not int
                or not graph.valid()
                or (type(x) is int and not adaptive._I64_MIN <= x <= adaptive._I64_MAX)
                or (type(x) is float and not math.isfinite(x))
                or not adaptive._I64_MIN <= n <= adaptive._I64_MAX):
            counts["fallback_calls"] += 1
            return workloads.numeric_batch(x, n)
        try:
            result = variants[type(x)](x, n)
        except (OverflowError, ZeroDivisionError):
            counts["overflow_replays"] += 1
            counts["fallback_calls"] += 1
            return workloads.numeric_batch(x, n)
        counts["native_calls"] += 1
        return result

    return static_entry, counts, sources, sizes


def budget_probe(compiler, inner):
    """Same one-variant budget across a changing supported type distribution."""
    wrapped = adaptive.specialize(warmup=2, max_variants=1, compiler=compiler,
                                 helpers={"numeric_step": workloads.numeric_step})(workloads.numeric_batch)
    for value in (3, 5, 7):
        if wrapped(value, inner) != workloads.numeric_batch(value, inner):
            raise RuntimeError("budget warmup mismatch")
    before = wrapped.adaptive_stats()
    for value in (0.25, 0.5, 1.25, 2.5) * 2:
        expected = workloads.numeric_batch(value, inner)
        actual = wrapped(value, inner)
        if type(actual) is not type(expected) or actual != expected:
            raise RuntimeError("budget shift mismatch")
    after = wrapped.adaptive_stats()
    if len(after["variants"]) != 1 or after["compile_failures"]:
        raise RuntimeError(f"budget probe failed: {after}")
    if after["native_hits"] != before["native_hits"] or after["fallbacks"] - before["fallbacks"] != 8:
        raise RuntimeError("one-slot budget must preserve Python fallback for late float phase")
    return {"before_shift": before, "after_shift": after,
            "interpretation": "The first compiled int signature exhausts the fixed attempt budget; later floats remain Python. No eviction/recompilation is claimed."}


def evaluate(args, profile):
    selected = profile.get("selected_region")
    if not selected or selected.get("name", selected.get("function")) != "numeric_batch":
        raise RuntimeError(f"No implemented profile-selected numeric region: {selected!r}")
    compiler = shlex.split(args.compiler)
    if not compiler:
        raise ValueError("empty compiler command")
    cpu = platform.processor()
    try:
        cpu = next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name"))
    except (OSError, StopIteration):
        pass
    llvm = Path(os.environ.get("PYSTACHY_LLVM", ""))
    clang = str(llvm / "clang") if str(llvm) != "." else "clang"
    report = {
        "schema_version": 1, "profile": profile, "selection": selected,
        "metadata": {"host_python": sys.version, "platform": platform.platform(),
                     "cpu_model": cpu, "cpu_count": os.cpu_count(),
                     "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
                     "clang_version": execute([clang, "--version"], dict(os.environ), 10)["stdout"].splitlines()[0],
                     "environment": {key: os.environ[key] for key in ("PYSTACHY_LLVM", "PYSTACHY_OPT", "PYSTACHY_CFLAGS", "PYSTACHY_GC", "PYSTACHY_GC_STRESS", "PYSTACHY_JIT_INLINE") if key in os.environ},
                     "compiler": compiler, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                     "revision": execute(["git", "rev-parse", "HEAD"], dict(os.environ), 10)["stdout"].strip(),
                     "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                       for name in ("tools/adaptive.py", "tools/adaptive_profile.py", "tools/adaptive_regions.py", "examples/adaptive/workloads.py")}},
        "settings": {"inner": args.inner, "batches": args.batches, "samples": args.samples,
                     "warmup": 3, "max_variants": 2, "cache_states": ["fresh", "populated"]},
        "method": "CPython orchestration and output construction are included in every application sample. Independent oracle computation and equality checks are outside timing. No type/hotness tracing runs during performance samples. Static types are supplied before observing values; its Python boundary retains safety/fallback checks. Shared host results have no timing thresholds.",
        "type_resolution": {"adaptive_entry": "Exact int/int and float/int types observed at the CPython boundary",
                            "static_entry": "The same two entry signatures are explicitly supplied before observing application values",
                            "helpers": "Unannotated numeric_step parameters are inferred statically from the typed entry and range loop in every native region",
                            "additional_signature_coverage_from_caller_cloning": False},
        "runs": [],
    }
    with tempfile.TemporaryDirectory(prefix="pystachy-regions-") as temporary:
        directory = Path(temporary)
        for cache_state in ("fresh", "populated"):
            modes = {"cpython": workloads.run_numeric}
            wrappers = {}
            cold, cache_priming = {}, {}
            expected_steady = workloads.run_numeric("steady", args.batches, inner=args.inner)
            for boundary, function, helpers in (
                ("leaf", workloads.numeric_step, {}),
                ("region", workloads.numeric_batch, {"numeric_step": workloads.numeric_step}),
            ):
                cache = directory / f"cache-{cache_state}-{boundary}"
                with compiler_cache(cache):
                    if cache_state == "populated":
                        prime = adaptive.specialize(warmup=1, compiler=compiler)(workloads.numeric_step)
                        prime(3, 1)
                        if not prime.adaptive_stats()["variants"]:
                            raise RuntimeError(f"cache prime failed: {prime.adaptive_stats()}")
                        cache_priming[boundary] = prime.adaptive_stats()["compile_seconds"]
                    start = time.perf_counter()
                    wrapped = adaptive.specialize(warmup=3, max_variants=2, compiler=compiler, helpers=helpers)(function)
                    app = application(wrapped, boundary)
                    elapsed = checked_run(app, "steady", args.batches, args.inner, expected_steady)
                    total = time.perf_counter() - start
                state = wrapped.adaptive_stats()
                if len(state["variants"]) != 2 or state["compile_failures"] or state["disabled_reason"]:
                    raise RuntimeError(f"{boundary} requires two real native variants: {state}")
                wrappers[boundary] = wrapped
                modes[boundary] = app
                cold[boundary] = {"first_application_s": elapsed, "wrapper_setup_and_first_application_wall_s": total,
                                  "profile_setup_and_first_application_wall_s": profile["total_profile_evaluation_wall_s"] + total,
                                  "compile_import_s": state["compile_seconds"], "dispatch_after_first_application": state}

            cache = directory / f"cache-{cache_state}-static"
            with compiler_cache(cache):
                if cache_state == "populated":
                    prime = adaptive.specialize(warmup=1, compiler=compiler)(workloads.numeric_step)
                    prime(3, 1)
                    if not prime.adaptive_stats()["variants"]:
                        raise RuntimeError("static cache prime failed")
                    cache_priming["static"] = prime.adaptive_stats()["compile_seconds"]
                start = time.perf_counter()
                static, static_counts, static_sources, static_sizes = compile_static_region(compiler, directory)
                compile_time = time.perf_counter() - start
                modes["static"] = application(static, "region")
                first_time = checked_run(modes["static"], "steady", args.batches, args.inner, expected_steady)
                cold["static"] = {"compile_import_s": compile_time, "first_application_s": first_time,
                                  "compile_and_first_application_s": compile_time + first_time}
            if static_sources != wrappers["region"].adaptive_stats()["sources"]:
                raise RuntimeError("static and runtime-discovered regions must generate identical source")

            phases = []
            for phase in workloads.PHASES:
                timings = {mode: [] for mode in modes}
                before = {mode: wrapper.adaptive_stats() for mode, wrapper in wrappers.items()}
                static_before = dict(static_counts)
                items = list(modes.items())
                for sample in range(args.samples):
                    offset = sample % len(items)
                    for mode, function in items[offset:] + items[:offset]:
                        timings[mode].append(checked_run(function, phase, args.batches, args.inner))
                after = {mode: wrapper.adaptive_stats() for mode, wrapper in wrappers.items()}
                dispatch = {mode: {key: after[mode][key] - before[mode][key]
                                   for key in ("native_hits", "fallbacks", "compile_failures", "compile_seconds")}
                            for mode in wrappers}
                dispatch["static"] = {key: static_counts[key] - static_before[key] for key in static_counts}
                if phase in ("steady", "shifted") and any(value["native_hits"] <= 0 or value["fallbacks"] for mode, value in dispatch.items() if mode != "static"):
                    raise RuntimeError("supported phase must actually use native code without fallback")
                if phase in ("steady", "shifted") and (dispatch["static"]["native_calls"] != args.samples * args.batches or dispatch["static"]["fallback_calls"]):
                    raise RuntimeError("static baseline must actually use native code without fallback")
                if phase == "unseen" and any(value["fallbacks"] <= 0 for mode, value in dispatch.items() if mode != "static"):
                    raise RuntimeError("held-out bool/large-int inputs must exercise Python fallback")
                if phase == "unseen" and dispatch["static"]["fallback_calls"] <= 0:
                    raise RuntimeError("static boundary must exercise held-out Python fallback")
                stats = {mode: summary(values) for mode, values in timings.items()}
                for mode in stats:
                    stats[mode]["speedup_vs_cpython"] = stats["cpython"]["median_s"] / stats[mode]["median_s"]
                phases.append({"phase": phase, "samples_s": timings, "summary": stats, "dispatch_deltas": dispatch})
            run = {"cache_state": cache_state, "cache_prime_compile_s_excluded": cache_priming,
                   "cold": cold, "phases": phases,
                   "static_extension_artifact_bytes": static_sizes,
                   "final_dispatch": {mode: wrapper.adaptive_stats() for mode, wrapper in wrappers.items()}}
            # Measured payback uses whole-application savings, not leaf timings.
            steady = phases[0]["summary"]
            run["estimated_applications_to_amortize_compile"] = {
                mode: cold[mode]["compile_import_s"] / (steady["cpython"]["median_s"] - steady[mode]["median_s"])
                if steady["cpython"]["median_s"] > steady[mode]["median_s"] else None
                for mode in ("leaf", "region", "static")}
            report["runs"].append(run)
        with compiler_cache(directory / "cache-populated-region"):
            report["one_variant_phase_budget"] = budget_probe(compiler, min(args.inner, 256))
    report["status"] = "passed"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inner", type=positive, default=4096)
    parser.add_argument("--batches", type=positive, default=24)
    parser.add_argument("--samples", type=positive, default=7)
    parser.add_argument("--profile-iterations", type=positive, default=24)
    parser.add_argument("--compiler", default=shlex.join([sys.executable, str(ROOT / "pystachy.py")]))
    parser.add_argument("--json", type=Path, default=ROOT / "build" / "adaptive-regions.json")
    args = parser.parse_args(argv)
    if args.batches < 12:
        parser.error("batches must be at least 12 to warm both signatures")
    from adaptive_profile import run_profiles
    start = time.perf_counter()
    profile = run_profiles(iterations=args.profile_iterations, samples=3, numeric_inner=args.inner)
    profile["total_profile_evaluation_wall_s"] = time.perf_counter() - start
    report = evaluate(args, profile)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("| cache | phase | CPython ms | leaf ms | region ms | static ms |")
    print("|---|---|---:|---:|---:|---:|")
    for run in report["runs"]:
        for phase in run["phases"]:
            values = [phase["summary"][mode]["median_s"] * 1000 for mode in ("cpython", "leaf", "region", "static")]
            print(f"| {run['cache_state']} | {phase['phase']} | " + " | ".join(f"{value:.4g}" for value in values) + " |")
    print(f"Checked all application outputs and actual native dispatch; full report: {args.json}")


if __name__ == "__main__":
    main()
