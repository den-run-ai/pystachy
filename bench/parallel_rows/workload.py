"""Row benchmark: KIND WORKERS ROWS WIDTH BATCHES WARMUPS.

WORKERS=0 is an ordinary specialized loop; positive values use sum_rows_float.
Each timed batch includes fresh output allocation and synchronous dispatch/join.
Input construction and complete bit-pattern output validation are outside timing.
"""
import sys
from struct import pack
from time import perf_counter

from parallel import sum_rows_float


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


def run_score(values: list[float], width: int, workers: int) -> list[float]:
    if workers != 0:
        return sum_rows_float(score, values, width, workers)
    result: list[float] = []
    for row in range(len(values) // width):
        total = 0.0
        for column in range(width):
            total = total + score(values[row * width + column])
        result.append(total)
    return result


def run_affine(values: list[float], width: int, workers: int) -> list[float]:
    if workers != 0:
        return sum_rows_float(affine, values, width, workers)
    result: list[float] = []
    for row in range(len(values) // width):
        total = 0.0
        for column in range(width):
            total = total + affine(values[row * width + column])
        result.append(total)
    return result


def execute(kind: str, values: list[float], width: int, workers: int) -> list[float]:
    if kind == 'score':
        return run_score(values, width, workers)
    return run_affine(values, width, workers)


def main() -> None:
    kind = sys.argv[1]
    workers = int(sys.argv[2])
    rows = int(sys.argv[3])
    width = int(sys.argv[4])
    batches = int(sys.argv[5])
    warmups = int(sys.argv[6])
    values = [float((i * 17) % 4096) * 0.00048828125 - 1.0 for i in range(rows * width)]
    for unused in range(warmups):
        execute(kind, values, width, workers)
    result: list[float] = []
    for unused in range(batches):
        start = perf_counter()
        result = execute(kind, values, width, workers)
        print('seconds', perf_counter() - start)
    expected = execute(kind, values, width, 0)
    if len(result) != rows or result is values:
        raise ValueError('expected a fresh result containing every row')
    bits: list[str] = []
    for row in range(rows):
        value_bits = pack('>d', result[row]).hex()
        if value_bits != pack('>d', expected[row]).hex():
            raise ValueError('row differs from the sequential reduction by bits')
        bits.append(value_bits)
    for i in range(len(values)):
        if values[i] != float((i * 17) % 4096) * 0.00048828125 - 1.0:
            raise ValueError('worker mutated its input')
    print('witness', ''.join(bits))


main()
