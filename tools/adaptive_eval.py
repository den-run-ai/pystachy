"""Measure PR #374's adaptive prototype against the same code without runtime type discovery.

usage: python3 tools/adaptive_eval.py PR_CHECKOUT [--rounds N] [--json OUT.json]

PR_CHECKOUT is a checkout of PR #374 with its compiler built (make): its tools/adaptive.py and
./pystachy. Numba and pyperformance are optional; their rows are skipped when they are missing.
Times exclude compilation. Each mode runs in interleaved rounds, and a round is the median of its
calls; the report gives the median round. Pin the process to one CPU (taskset -c 3 ...) on a shared host.

1. weighted_sum(x, n), the PR's demo kernel, for (int, int) and (float, int): CPython, the adaptive
   wrapper, the source it generates built by pystachy ext and called directly, numba.njit, and whole
   programs through pystachy run (JIT) and build (AOT), annotated and unannotated (a template).
2. The cost of one call of a small function: spectral_norm's eval_A, and add.
3. pyperformance's spectral_norm, whose eval_A is the one function of the census corpus that the
   prototype accepts (docs/archive/type-feedback-census.md), with eval_A offloaded each way.
"""
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
import types

WEIGHTED_SUM = """\
def weighted_sum(x, n):
    total = x
    for i in range(n):
        total += (i % 17) * x
    return total
"""
SMALL = {
    "eval_A": "def eval_A(i, j):\n    return 1.0 / ((i + j) * (i + j + 1) // 2 + i + 1)\n",
    "add": "def add(a, b):\n    return a + b\n",
}
PROGRAM = """\
import sys
from time import perf_counter_ns
{kernel}

def main() -> None:
    n = int(sys.argv[1])
    reps = int(sys.argv[2])
    times: list[int] = []
    check = {zero}
    for k in range(reps):
        t = perf_counter_ns()
        r = weighted_sum({x0!r} + k, n)
        times.append(perf_counter_ns() - t)
        check += r
    times.sort()
    print(times[len(times) // 2], check)

main()
"""


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Setup:
    def __init__(self, checkout, work):
        self.checkout, self.work = checkout, work
        self.compiler = os.path.join(checkout, "pystachy")
        self.built = {}  # an extension module loads once per process (docs/reference/ffi.md)
        sys.path.insert(0, os.path.join(checkout, "tools"))

    def adaptive(self, name, source):
        """The kernel in a module of its own, as an application would import it."""
        path = os.path.join(self.work, name + "_kernel.py")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(f"from adaptive import specialize\n\n\n@specialize(warmup=3, max_variants=2, "
                         f"compiler=[{self.compiler!r}])\n{source}")
        return getattr(load(path, name + "_kernel"), name)

    def direct(self, wrapped, signature):
        """The source the wrapper generated for signature, built by pystachy ext and imported."""
        stats = wrapped.adaptive_stats()
        if signature not in stats["variants"]:
            raise SystemExit(f"no native variant for {signature}: {stats['disabled_reason'] or stats['compile_errors']}")
        name = "direct_" + wrapped.__name__ + "_" + signature.replace(",", "_")
        if name in self.built:
            return self.built[name]
        source = os.path.join(self.work, name + ".py")
        with open(source, "w", encoding="utf-8") as stream:
            stream.write(stats["sources"][signature])
        subprocess.run([self.compiler, "ext", source, "-o", os.path.join(self.work, name + ".abi3.so")], check=True)
        self.built[name] = load(os.path.join(self.work, name + ".abi3.so"), name).kernel
        return self.built[name]


def rounds(modes, call, reps, count):
    """Median per round of each mode, interleaving the modes; returns the median round in ns."""
    times = {name: [] for name in modes}
    for _ in range(count):
        for name, f in modes.items():
            samples = []
            for k in range(reps):
                samples.append(call(f, k))
            times[name].append(statistics.median(samples))
    return {name: round(statistics.median(v)) for name, v in times.items()}


def kernel_modes(setup, numba, count):
    n, reps = 200_000, 9
    wrapped = setup.adaptive("weighted_sum", WEIGHTED_SUM)
    results = {}
    for x0, ann in ((3, "int"), (0.5, "float")):
        signature = f"{ann},int"
        for _ in range(3):
            wrapped(x0, n)
        modes = {"CPython": wrapped.__wrapped__, "adaptive wrapper": wrapped, "ext, called directly": setup.direct(wrapped, signature)}
        if numba:
            modes["numba.njit"] = numba.njit(wrapped.__wrapped__)
            modes["numba.njit"](x0, n)
        expected = wrapped.__wrapped__(x0, n)
        for name, f in modes.items():
            got = f(x0, n)
            assert type(got) is type(expected) and got == expected, (name, got, expected)

        def call(f, k, x0=x0):
            t = time.perf_counter_ns()
            f(x0 + (k & 3), n)
            return time.perf_counter_ns() - t
        row = rounds(modes, call, reps, count)
        for variant, header in (("annotated", f"def weighted_sum(x: {ann}, n: int) -> {ann}:"), ("unannotated", None)):
            kernel = WEIGHTED_SUM if header is None else WEIGHTED_SUM.replace("def weighted_sum(x, n):", header)
            source = os.path.join(setup.work, f"program_{variant}_{ann}.py")
            with open(source, "w", encoding="utf-8") as stream:
                stream.write(PROGRAM.format(kernel=kernel, zero="0" if ann == "int" else "0.0", x0=x0))
            exe = source[:-3]
            subprocess.run([setup.compiler, "build", source, "-o", exe], check=True)
            for mode, argv in (("JIT", [setup.compiler, "run", source]), ("AOT", [exe])):
                medians = []
                for _ in range(count):
                    out = subprocess.run(argv + [str(n), str(reps)], capture_output=True, text=True, check=True).stdout.split()
                    medians.append(int(out[0]))
                row[f"Pystachy {mode}, {variant}"] = round(statistics.median(medians))
        results[signature] = row
    return results


def small_modes(setup, numba, count):
    results = {}
    inner = 20_000

    def call(f, k):
        t = time.perf_counter_ns()
        for _ in range(inner):
            f(7 + (k & 3), 11)
        return (time.perf_counter_ns() - t) / inner
    for name, source in SMALL.items():
        wrapped = setup.adaptive(name, source)
        for _ in range(4):
            wrapped(7, 11)
        modes = {"CPython": wrapped.__wrapped__, "adaptive wrapper": wrapped, "ext, called directly": setup.direct(wrapped, "int,int")}
        if numba:
            modes["numba.njit"] = numba.njit(wrapped.__wrapped__)
            modes["numba.njit"](7, 11)
        results[name + "(int, int)"] = rounds(modes, call, 9, count)
    return results


def spectral_norm(setup, numba, count):
    try:
        import pyperformance
    except ImportError:
        return None
    script = os.path.join(os.path.dirname(pyperformance.__file__), "data-files", "benchmarks", "bm_spectral_norm", "run_benchmark.py")
    stand_in = types.ModuleType("pyperf")  # the benchmark only needs pyperf's clock
    stand_in.perf_counter = time.perf_counter
    sys.modules.setdefault("pyperf", stand_in)
    modes = {"CPython": load(script, "sn_cpython")}
    adaptive = load(script, "sn_adaptive")
    adaptive.eval_A = setup.adaptive("eval_A", SMALL["eval_A"])
    for _ in range(4):
        adaptive.eval_A(1, 2)
    modes["adaptive wrapper"] = adaptive
    direct = load(script, "sn_direct")
    direct.eval_A = setup.direct(adaptive.eval_A, "int,int")
    modes["ext, called directly"] = direct
    if numba:
        jitted = load(script, "sn_numba")
        jitted.eval_A = numba.njit(jitted.eval_A)
        jitted.eval_A(1, 2)
        modes["numba.njit"] = jitted
    return rounds(modes, lambda m, k: m.bench_spectral_norm(1) * 1e9, 1, count)


def show(title, rows, unit, scale):
    print(f"\n{title}\n")
    columns = list(next(iter(rows.values())))
    print("| mode | " + " | ".join(rows) + " |")
    print("|---|" + "---:|" * len(rows))
    for column in columns:
        cells = []
        for row in rows.values():
            base = row["CPython"]
            cells.append(f"{row[column] / scale:,.1f} {unit} ({base / row[column]:.2f}x)")
        print(f"| {column} | " + " | ".join(cells) + " |")


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    count = int(args[args.index("--rounds") + 1]) if "--rounds" in args else 7
    out = args[args.index("--json") + 1] if "--json" in args else ""
    checkout = os.path.abspath(args[0])
    try:
        import numba
    except ImportError:
        numba = None
    with tempfile.TemporaryDirectory(prefix="adaptive-eval-") as work:
        setup = Setup(checkout, work)
        report = {"weighted_sum": kernel_modes(setup, numba, count), "small": small_modes(setup, numba, count),
                  "spectral_norm": spectral_norm(setup, numba, count)}
    show("weighted_sum(x, 200_000): median time per call (speed relative to CPython)", report["weighted_sum"], "us", 1e3)
    show("One call of a small function", report["small"], "ns", 1)
    if report["spectral_norm"]:
        show("spectral_norm with eval_A offloaded: one benchmark iteration", {"spectral_norm": report["spectral_norm"]}, "ms", 1e6)
    if out:
        with open(out, "w", encoding="utf-8") as stream:
            json.dump(report, stream, indent=1)


if __name__ == "__main__":
    main()
