"""Fixed-width integer arithmetic. The inputs vary at runtime and are built before timing."""
import sys
from time import perf_counter


def floordiv(n: int, xs: list[int], ys: list[int]) -> int:
    total = 0
    for i in range(n):
        total += xs[i & 255] // ys[i & 255]
    return total


def modulo(n: int, xs: list[int], ys: list[int]) -> int:
    total = 0
    for i in range(n):
        total += xs[i & 255] % ys[i & 255]
    return total


def lshift(n: int, xs: list[int], counts: list[int]) -> int:
    total = 0
    for i in range(n):
        total += xs[i & 255] << counts[i & 255]
    return total


def rshift(n: int, xs: list[int], counts: list[int]) -> int:
    total = 0
    for i in range(n):
        total += xs[i & 255] >> counts[i & 255]
    return total


def bit_length(n: int, xs: list[int]) -> int:
    total = 0
    for i in range(n):
        total += xs[i & 255].bit_length()
    return total


def bit_count(n: int, xs: list[int]) -> int:
    total = 0
    for i in range(n):
        total += xs[i & 255].bit_count()
    return total


def true_divide(n: int, xs: list[int], ys: list[int]) -> float:
    total = 0.0
    for i in range(n):
        total += xs[i & 255] / ys[i & 255]
    return total


kind = sys.argv[1]
n = int(sys.argv[2])
small = [(i * 16411) % 65537 - 32768 for i in range(256)]
denoms = [2 * ((i * 67) % 257) - 255 for i in range(256)]
wide = [((1 << (54 + i % 9)) + i * 6700417) * (-1 if i & 1 else 1) for i in range(256)]
wide_denoms = [((1 << (54 + i % 7)) + 1 + i * 65537) * (-1 if i & 2 else 1) for i in range(256)]
left_counts = [(i * 17) % 21 for i in range(256)]
right_counts = [(i * 17) % 68 for i in range(256)]

int_sum = 0
float_sum = 0.0
start = perf_counter()
if kind == "floordiv":
    int_sum = floordiv(n, wide, wide_denoms)
elif kind == "modulo":
    int_sum = modulo(n, wide, denoms)
elif kind == "lshift":
    int_sum = lshift(n, small, left_counts)
elif kind == "rshift":
    int_sum = rshift(n, small, right_counts)
elif kind == "bit-length":
    int_sum = bit_length(n, wide)
elif kind == "bit-count":
    int_sum = bit_count(n, wide)
elif kind == "idiv-small":
    float_sum = true_divide(n, small, denoms)
elif kind == "idiv-wide":
    float_sum = true_divide(n, wide, wide_denoms)
else:
    raise ValueError("unknown workload")
elapsed = perf_counter() - start
print(float_sum.hex() if kind.startswith("idiv-") else str(int_sum), elapsed)
