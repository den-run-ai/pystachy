import sys
from time import perf_counter_ns


def step(value: int, salt: int) -> int:
    return ((value * 33) ^ salt) & 65535


def kernel(n: int) -> int:
    value = 17
    for i in range(n):
        value = step(value, i & 255)
    return value


n = int(sys.argv[1])
print("warm", kernel(n))
for sample in range(7):
    start = perf_counter_ns()
    result = kernel(n)
    elapsed = perf_counter_ns() - start
    print(result, elapsed)
