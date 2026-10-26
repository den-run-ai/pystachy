from mpz import mpz
import sys
import time


def run(n: int) -> mpz:
    values: list[mpz] = []
    big = mpz(1) << 64
    for i in range(n):
        values.append(mpz((i * 2654435761) % 4294967296) if i % 3 else big + i)
    values.sort()
    counts: dict[mpz, int] = {}
    for v in values:
        k = v % 1000
        counts[k] = counts.get(k, 0) + 1
    total = mpz(0)
    for v in values:
        total = total + v
    return total % 1000000007 + len(counts) + values[n // 2] % 1000


n = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
start = time.perf_counter()
r = run(n)
elapsed = time.perf_counter() - start
print(str(r))
print(elapsed)
