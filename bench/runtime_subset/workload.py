"""Native runtime migration kernels; timed region excludes input construction."""
import math
import sys
from time import perf_counter


def scalar(n: int) -> float:
    total = 0.0
    for i in range(n):
        x = float(i % 1024) * 0.125 + 0.1
        converted = math.degrees(math.radians(x))
        total += converted + float(math.isclose(converted, x, rel_tol=1e-15))
    return total


def ranges(n: int) -> float:
    total = 0
    for i in range(n):
        start = i % 1024 - 512
        step = i % 7 + 1
        total += len(range(start, 2048, step))
        total += int((i % 127) in range(start, 2048, step))
        total += len(range(2048, start, -step))
    return float(total)


def powers(n: int) -> float:
    total = 0
    for i in range(n):
        total += (i % 5 - 2) ** (i % 12)
    return float(total)


def sum_float(n: int, xs: list[float]) -> float:
    total = 0.0
    for i in range(n):
        total += sum(xs, float(i % 7))
    return total


def sum_int(n: int, xs: list[float]) -> float:
    total = 0.0
    for i in range(n):
        total += sum(xs, i % 7)
    return total


def tail_absolute(xs: list[float], start: float) -> float:
    total = start
    for i in range(1, len(xs)):
        total += abs(xs[i])
    return total


def reduction(n: int, xs: list[float]) -> float:
    total = 0.0
    for i in range(n):
        total += tail_absolute(xs, float(i % 7))
    return total


def escape(n: int, text: str) -> float:
    total = 0
    for i in range(n):
        # Vary the input to prevent a pure representation from being hoisted.
        rendered = ascii(str(i % 7) + text)
        # Consume the bytes as well as their length, retaining output stores.
        total += len(rendered) + rendered.count("\\") + ord(rendered[1])
    return float(total)


kind = sys.argv[1]
n = int(sys.argv[2])
xs: list[float] = []
text = ""
if kind == "sum-float" or kind == "sum-int":
    xs = [1e16, 1.0, -1e16, 0.25] * 8192
elif kind == "reduction":
    xs = [1.0, -2.0, 3.0, -4.0] * 8192
elif kind == "ascii":
    text = "the quick brown fox jumps over the lazy dog " * 100
elif kind == "unicode":
    text = "aé€𝄞" * 1024

begin = perf_counter()
value = 0.0
if kind == "scalar":
    value = scalar(n)
elif kind == "range":
    value = ranges(n)
elif kind == "power":
    value = powers(n)
elif kind == "sum-float":
    value = sum_float(n, xs)
elif kind == "sum-int":
    value = sum_int(n, xs)
elif kind == "reduction":
    value = reduction(n, xs)
elif kind == "ascii" or kind == "unicode":
    value = escape(n, text)
else:
    raise ValueError("unknown workload")
elapsed = perf_counter() - begin
print(value.hex(), elapsed)
