# pystachy: python-int
# Values that cross the int64 boundary and come back: promotion and demotion.
import sys
import time


def run(n: int) -> int:
    x = 9223372036854775000
    total = 0
    for i in range(n):
        y = x + i * 7
        z = y - 9223372036854775000
        total += z & 1023
    return total


n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000000
start = time.perf_counter()
r = run(n)
elapsed = time.perf_counter() - start
print(r)
print(elapsed)
