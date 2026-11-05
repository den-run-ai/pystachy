"""Independent float scores: WORKLOAD WORKERS ITEMS BATCHES WARMUPS.

WORKERS=0 selects an ordinary for loop; positive values select map_float.
Inputs repeat every 1,024 elements, so the witness covers every distinct input.
Allocation, dispatch and scoring are timed; construction and checking are not.
"""
import sys
from time import perf_counter

from parallel import map_float


def score(x: float) -> float:
    # A synthetic degree-32 polynomial score, written out because the initial
    # worker verifier does not accept backedges. Strict float ordering matters.
    y = 0.125
    y = y * x + 0.0625
    y = y * x - 0.03125
    y = y * x + 0.015625
    y = y * x - 0.0078125
    y = y * x + 0.00390625
    y = y * x - 0.001953125
    y = y * x + 0.0009765625
    y = y * x - 0.00048828125
    y = y * x + 0.0625
    y = y * x - 0.03125
    y = y * x + 0.015625
    y = y * x - 0.0078125
    y = y * x + 0.00390625
    y = y * x - 0.001953125
    y = y * x + 0.0009765625
    y = y * x - 0.00048828125
    y = y * x + 0.0625
    y = y * x - 0.03125
    y = y * x + 0.015625
    y = y * x - 0.0078125
    y = y * x + 0.00390625
    y = y * x - 0.001953125
    y = y * x + 0.0009765625
    y = y * x - 0.00048828125
    y = y * x + 0.0625
    y = y * x - 0.03125
    y = y * x + 0.015625
    y = y * x - 0.0078125
    y = y * x + 0.00390625
    y = y * x - 0.001953125
    y = y * x + 0.0009765625
    y = y * x - 0.00048828125
    return y


def affine(x: float) -> float:
    # Cheap control: allocation, memory traffic and dispatch can dominate.
    return x * 0.75 + 0.125


def run_score(values: list[float], workers: int) -> list[float]:
    if workers == 0:
        result: list[float] = []
        for value in values:
            result.append(score(value))
        return result
    return map_float(score, values, workers)


def run_affine(values: list[float], workers: int) -> list[float]:
    if workers == 0:
        result: list[float] = []
        for value in values:
            result.append(affine(value))
        return result
    return map_float(affine, values, workers)


def execute(kind: str, values: list[float], workers: int) -> list[float]:
    if kind == "score":
        return run_score(values, workers)
    return run_affine(values, workers)


def validate(values: list[float], result: list[float], expected: list[float]) -> float:
    if result is values or len(result) != len(values):
        raise ValueError("expected a fresh result with unchanged length")
    total = 0.0
    for i in range(len(result)):
        # Each comparison also rejects NaN against the finite reference values.
        if result[i] != expected[i % 1024]:
            raise ValueError("ordered result differs from the scalar reference")
        if values[i] != float(i % 1024) * 0.001953125 - 1.0:
            raise ValueError("mapping changed an input")
        total += result[i]
    return total


def main() -> None:
    kind = sys.argv[1]
    workers = int(sys.argv[2])
    n = int(sys.argv[3])
    batches = int(sys.argv[4])
    warmups = int(sys.argv[5])
    if kind not in ("score", "affine"):
        raise ValueError("workload must be score or affine")
    if workers < 0 or workers > 64 or n < 0 or batches < 0 or warmups < 0:
        raise ValueError("invalid worker count, input size or repetitions")
    values = [float(i % 1024) * 0.001953125 - 1.0 for i in range(n)]
    distinct = [float(i) * 0.001953125 - 1.0 for i in range(1024)]
    expected = execute(kind, distinct, 0)
    result = execute(kind, values, workers)
    checksum = validate(values, result, expected)
    print("workload", kind)
    print("workers", workers)
    print("items", n)
    print("checksum", checksum)
    print("witness", repr(result[:1024]))
    for batch in range(warmups + batches):
        previous = result
        start = perf_counter()
        result = execute(kind, values, workers)
        seconds = perf_counter() - start
        if result is previous:
            raise ValueError("mapping reused a previous result")
        if validate(values, result, expected) != checksum:
            raise ValueError("checksum changed between batches")
        if batch >= warmups:
            print("seconds", seconds)


main()
