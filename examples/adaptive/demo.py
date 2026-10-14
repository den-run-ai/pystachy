"""Run an unannotated numeric kernel through the adaptive prototype."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from adaptive import specialize


@specialize(warmup=3, max_variants=2)
def weighted_sum(x, n):
    total = x
    for i in range(n):
        total += (i % 17) * x
    return total


def timed(function, args, samples):
    expected = weighted_sum.__wrapped__(*args)
    times = []
    for _ in range(samples):
        start = time.perf_counter()
        result = function(*args)
        times.append(time.perf_counter() - start)
        if type(result) is not type(expected) or result != expected:
            raise RuntimeError(f"wrong result: {result!r}, expected {expected!r}")
    return statistics.median(times)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=200_000)
    parser.add_argument("--samples", type=int, default=5)
    args = parser.parse_args()
    if args.iterations < 1 or args.samples < 1:
        parser.error("iterations and samples must be positive")

    measurements = []
    for x in (3, 0.5):
        values = (x, args.iterations)
        expected = weighted_sum.__wrapped__(*values)
        start = time.perf_counter()
        for _ in range(3):
            result = weighted_sum(*values)
            if type(result) is not type(expected) or result != expected:
                raise RuntimeError("warmup result differs from CPython")
        cold = time.perf_counter() - start
        python = timed(weighted_sum.__wrapped__, values, args.samples)
        adaptive = timed(weighted_sum, values, args.samples)
        measurements.append({
            "signature": [type(value).__name__ for value in values],
            "cold_three_calls_s": cold,
            "cpython_median_s": python,
            "adaptive_median_s": adaptive,
            "warm_speedup": python / adaptive,
        })

    # Both inputs exercise the original Python path: bool is not an exact int,
    # and the integer exceeds the native runtime's signed 64-bit representation.
    for values in ((True, 10), (2**80, 10)):
        if weighted_sum(*values) != weighted_sum.__wrapped__(*values):
            raise RuntimeError("fallback result differs from CPython")
    report = {"measurements": measurements, "dispatch": weighted_sum.adaptive_stats()}
    print(json.dumps(report, indent=2))
    if len(report["dispatch"]["variants"]) != 2:
        raise SystemExit("native variants were not built; inspect dispatch diagnostics")


if __name__ == "__main__":
    main()
