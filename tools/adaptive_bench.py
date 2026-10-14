"""Compare CPython, guarded specialization, direct extension, JIT and AOT.

One unannotated kernel and varying runtime inputs; cold setup is reported
separately from checked in-process compute samples. No performance thresholds.
"""

import argparse
import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import platform
import shlex
import statistics
import sys
import tempfile
import time
import uuid

import adaptive
from bench_extended import execute


ROOT = Path(__file__).resolve().parents[1]


def weighted_sum(x, n):
    total = x
    for i in range(n):
        total += (i % 17) * x
    return total


def inputs(kind, n, sample):
    x = 3 + sample if kind == "int" else 0.5 + sample * 0.25
    return x, n + sample * 17


def check(value, expected):
    if type(value) is not type(expected) or value != expected:
        raise RuntimeError(f"result {value!r} ({type(value).__name__}) differs from CPython {expected!r} ({type(expected).__name__})")


def timed(function, args, expected):
    start = time.perf_counter_ns()
    value = function(*args)
    elapsed = time.perf_counter_ns() - start
    check(value, expected)
    if elapsed <= 0:
        raise RuntimeError("nonpositive compute timing")
    return elapsed / 1e9


def summary(samples):
    median = statistics.median(samples)
    return {"median_s": median, "min_s": min(samples), "max_s": max(samples),
            "mad_s": statistics.median(abs(value - median) for value in samples)}


def standalone_source(kind):
    # The kernel stays unannotated. argv conversions establish argument types
    # for the existing compiler's static template specialization. Neither the
    # work count nor the multiplier is an LLVM-visible source constant.
    convert = "int" if kind == "int" else "float"
    offset = "sample" if kind == "int" else "sample * 0.25"
    return inspect.getsource(weighted_sum) + f'''
import sys
from time import perf_counter_ns

base_n = int(sys.argv[1])
samples = int(sys.argv[2])
base_x = {convert}(sys.argv[3])
value = weighted_sum(base_x, base_n)
print("warmup", "float" if isinstance(value, float) else "int", value)
for sample in range(samples):
    n = base_n + sample * 17
    x = base_x + {offset}
    start = perf_counter_ns()
    value = weighted_sum(x, n)
    elapsed = perf_counter_ns() - start
    print("sample", sample, "float" if isinstance(value, float) else "int", value, elapsed)
'''


def parse_samples(output, kind, oracle, first_expected):
    rows = [row.split() for row in output.splitlines()]
    if len(rows) != len(oracle) + 1 or len(rows[0]) != 3 or rows[0][:2] != ["warmup", kind]:
        raise RuntimeError("unexpected standalone output")
    check(ast.literal_eval(rows[0][2]), first_expected)
    timings = []
    for sample, (row, expected) in enumerate(zip(rows[1:], oracle, strict=True)):
        if len(row) != 5 or row[:3] != ["sample", str(sample), kind]:
            raise RuntimeError(f"unexpected sample row: {row}")
        check(ast.literal_eval(row[3]), expected)
        elapsed = int(row[4])
        if elapsed <= 0:
            raise RuntimeError("nonpositive standalone compute timing")
        timings.append(elapsed / 1e9)
    return timings


def run_signature(kind, wrapped, args, compiler, env, directory):
    signature = f"{kind},int"
    first_args = inputs(kind, args.iterations, 0)
    expected = weighted_sum(*first_args)
    before = wrapped.adaptive_stats()
    start = time.perf_counter()
    for _ in range(3):
        check(wrapped(*first_args), expected)
    adaptive_cold = time.perf_counter() - start
    state = wrapped.adaptive_stats()
    if signature not in state["variants"] or state["compile_failures"] or state["disabled_reason"]:
        raise RuntimeError(f"adaptive native specialization failed: {state}")

    # Compile exactly the generated typed extension, changing only its unique
    # module filename. Its body, ABI and optimizer are matched to the adaptive
    # variant; direct calls remove just the Python specialization wrapper.
    typed_source = state["sources"][signature]
    start = time.perf_counter()
    direct = adaptive._compile_variant(typed_source, compiler, directory, "_adaptive_direct_" + uuid.uuid4().hex)
    direct_cold = time.perf_counter() - start
    check(direct(*first_args), expected)

    values = [inputs(kind, args.iterations, sample) for sample in range(args.samples)]
    oracle = [weighted_sum(*value) for value in values]
    python_timings, guarded_timings, direct_timings = [], [], []
    # Rotate the host-side order between samples to reduce fixed-order drift.
    modes = [("cpython", weighted_sum, python_timings),
             ("adaptive", wrapped, guarded_timings), ("direct_ext", direct, direct_timings)]
    hits_before = wrapped.adaptive_stats()["native_hits"]
    for sample, (value, answer) in enumerate(zip(values, oracle, strict=True)):
        offset = sample % len(modes)
        for _, function, timings in modes[offset:] + modes[:offset]:
            timings.append(timed(function, value, answer))
    if wrapped.adaptive_stats()["native_hits"] - hits_before != args.samples:
        raise RuntimeError("adaptive timings include non-native fallbacks")

    program = directory / f"weighted_{kind}.py"
    program.write_text(standalone_source(kind), encoding="utf-8")
    binary = directory / f"weighted_{kind}"
    runargs = [str(args.iterations), str(args.samples), str(first_args[0])]
    aot_build = execute([*compiler, "build", str(program), "-o", str(binary)], env, args.timeout)
    jit = execute([*compiler, "run", str(program), *runargs], env, args.timeout)
    aot = execute([str(binary), *runargs], env, args.timeout)
    jit_timings = parse_samples(jit["stdout"], kind, oracle, expected)
    aot_timings = parse_samples(aot["stdout"], kind, oracle, expected)
    all_timings = {"cpython": python_timings, "adaptive": guarded_timings,
                   "direct_ext": direct_timings, "jit": jit_timings, "aot": aot_timings}
    summaries = {mode: summary(times) for mode, times in all_timings.items()}
    reference_median = summaries["cpython"]["median_s"]
    for mode, result in summaries.items():
        result["speedup_vs_cpython"] = reference_median / result["median_s"]
    return {
        "signature": signature,
        "inputs": [list(value) for value in values],
        "oracle": [{"type": type(value).__name__, "value": value} for value in oracle],
        "samples_s": all_timings,
        "warm_summary": summaries,
        "cold": {"adaptive_three_python_calls_and_compile_wall_s": adaptive_cold,
                 "adaptive_compile_import_s": state["compile_seconds"] - before["compile_seconds"],
                 "direct_ext_compile_import_wall_s": direct_cold,
                 "jit_process_wall_s": jit["wall_s"],
                 "aot_build_wall_s": aot_build["wall_s"], "aot_process_wall_s": aot["wall_s"]},
        "standalone_driver_sha256": hashlib.sha256(program.read_bytes()).hexdigest(),
        "typed_extension_source": typed_source,
        "processes": {"aot_build": aot_build, "jit": jit, "aot": aot},
    }


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=positive, default=200_000)
    parser.add_argument("--samples", type=positive, default=7)
    parser.add_argument("--compiler", default=shlex.join([sys.executable, str(ROOT / "pystachy.py")]), help="shell-split command; no shell evaluation")
    parser.add_argument("--timeout", type=positive, default=60, help="seconds per standalone command including LLVM children")
    parser.add_argument("--json", type=Path, help="also write the complete JSON report to this file")
    args = parser.parse_args(argv)
    compiler = shlex.split(args.compiler)
    if not compiler:
        parser.error("empty compiler command")
    compiler = [str(Path(value).resolve()) if index == 0 and "/" in value else value for index, value in enumerate(compiler)]
    env = dict(os.environ)
    env.setdefault("PYTHONHASHSEED", "0")
    report = {
        "schema_version": 1,
        "settings": {"iterations": args.iterations, "samples": args.samples, "warmup_calls": 3, "max_variants": 2, "timeout_s": args.timeout},
        "metadata": {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                     "host_python": sys.version, "platform": platform.platform(),
                     "machine": platform.machine(), "cpu_count": os.cpu_count(),
                     "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
                     "compiler_command": compiler,
                     "git_revision": execute(["git", "rev-parse", "HEAD"], env, args.timeout)["stdout"].strip(),
                     "environment": {key: env[key] for key in ("PYSTACHY_LLVM", "PYSTACHY_OPT", "PYSTACHY_CFLAGS", "PYTHONHASHSEED") if key in env},
                     "controller_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "kernel_source": inspect.getsource(weighted_sum),
        "method": "One varying-input kernel call per timed sample; type and value checked against CPython. Warm timers exclude printing/checking. JIT process wall includes compiler startup, lowering, execution and output. The CLI JIT runtime cache is primed before comparisons; AOT/extension setup can also reuse existing runtime caches. Costs are process-cold, not cache-cold.",
        "backends": {"adaptive": "Existing AOT extension pipeline plus exact-type wrapper guards",
                     "direct_ext": "The identical typed AOT extension source called directly",
                     "jit": "Existing CLI JIT with statically inferred template arguments",
                     "aot": "Existing CLI AOT with statically inferred template arguments"},
        "results": [],
    }
    wrapped = adaptive.specialize(warmup=3, max_variants=2, compiler=compiler)(weighted_sum)
    with tempfile.TemporaryDirectory(prefix="pystachy-adaptive-bench-") as temporary:
        startup = Path(temporary) / "startup.py"
        startup.write_text("pass\n", encoding="utf-8")
        report["runtime_cache_prime"] = execute([*compiler, "run", str(startup)], env, args.timeout)
        for kind in ("int", "float"):
            report["results"].append(run_signature(kind, wrapped, args, compiler, env, Path(temporary)))
    report["adaptive_dispatch"] = wrapped.adaptive_stats()
    if len(report["adaptive_dispatch"]["variants"]) != 2 or report["adaptive_dispatch"]["native_hits"] != 2 * args.samples:
        raise RuntimeError("benchmark requires two actual native adaptive variants")
    report["status"] = "passed"
    output = json.dumps(report, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(output + "\n", encoding="utf-8")
        print("| signature | CPython ms | adaptive ms | direct ext ms | JIT ms | AOT ms |")
        print("|---|---:|---:|---:|---:|---:|")
        for result in report["results"]:
            columns = [result["warm_summary"][mode]["median_s"] * 1000 for mode in ("cpython", "adaptive", "direct_ext", "jit", "aot")]
            print("| " + result["signature"] + " | " + " | ".join(f"{value:.4g}" for value in columns) + " |")
        print(f"Checked {report['adaptive_dispatch']['native_hits']} adaptive native calls; setup costs and all samples: {args.json}")
    else:
        print(output)


if __name__ == "__main__":
    main()
