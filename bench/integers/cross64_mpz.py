from mpz import mpz
import sys
import time


def run(n: int) -> mpz:
    x = mpz("9223372036854775000")
    base = mpz("9223372036854775000")
    total = mpz(0)
    for i in range(n):
        y = x + i * 7
        z = y - base
        total = total + (z & 1023)
    return total


n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000000
start = time.perf_counter()
r = run(n)
elapsed = time.perf_counter() - start
print(str(r))
print(elapsed)
