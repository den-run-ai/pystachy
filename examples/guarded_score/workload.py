"""Runtime-selected batch scores; shared unchanged by both benchmark variants."""
from collections.abc import Callable
import sys
from time import perf_counter_ns, process_time_ns

from scoring import absolute_error, squared_error


def weighted_error(scale: float) -> Callable[[float, float], float]:
    def error(predicted: float, expected: float) -> float:
        difference = predicted - expected
        return scale * (difference * difference)
    return error


def inputs(size: int, seed: int) -> tuple[list[float], list[float]]:
    predicted: list[float] = []
    expected: list[float] = []
    for index in range(size):
        # Binary fractions keep the finite benchmark checksums exact. The seed
        # and dimensions come from argv, and every score contributes to output.
        predicted.append(float((index * 17 + seed) % 257) / 16.0)
        expected.append(float((index * 13 + seed * 3) % 127) / 16.0)
    return predicted, expected


def callbacks(scenario: str, batches: int) -> list[Callable[[float, float], float]]:
    first = weighted_error(0.5)
    second = weighted_error(1.5)
    selected: list[Callable[[float, float], float]] = []
    for batch in range(batches):
        callback: Callable[[float, float], float] = squared_error
        if scenario == "absolute":
            callback = absolute_error
        elif scenario == "skew99" and batch % 100 == 99:
            callback = first
        elif scenario == "mixed" and batch % 2 == 1:
            callback = absolute_error
        elif scenario == "miss":
            callback = first
        elif scenario == "change" and batch >= batches // 2:
            callback = first if batch % 2 == 0 else second
        selected.append(callback)
    return selected


def run(scorer) -> None:
    scenario = sys.argv[1]
    size = int(sys.argv[2])
    batches = int(sys.argv[3])
    seed = int(sys.argv[4])
    if scenario not in ["square", "absolute", "skew99", "mixed", "miss", "change", "stream"]:
        raise ValueError("unknown scoring scenario")
    if size < 0 or batches < 1 or seed < 0 or seed > 1000000:
        raise ValueError("expected nonnegative size, positive batches and seed in 0..1000000")
    predicted, expected = inputs(size, seed)
    selected = callbacks(scenario, batches)
    # One untimed call warms instruction/data access in every process. Measured
    # work includes selection, the length check, entry guard and complete loop.
    scorer(selected[0], predicted, expected)
    total = 0.0
    wall_start = perf_counter_ns()
    cpu_start = process_time_ns()
    for batch in range(batches):
        if scenario == "stream":
            # Construction-heavy control: include fresh input allocation and
            # conversion in the measured region, as an application would.
            predicted, expected = inputs(size, seed + batch % 97)
        total += scorer(selected[batch], predicted, expected)
    cpu_elapsed = process_time_ns() - cpu_start
    wall_elapsed = perf_counter_ns() - wall_start
    print(total)
    print(size * batches)
    print("kernel_wall_ns", wall_elapsed, file=sys.stderr)
    print("kernel_cpu_ns", cpu_elapsed, file=sys.stderr)
