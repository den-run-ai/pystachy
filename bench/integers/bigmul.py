# pystachy: python-int
# Large operands: squaring and dividing ~6000-digit integers (CPython uses Karatsuba).
import sys
import time


def run(reps: int) -> int:
    x = 3 ** 12000
    m = 7 ** 3000 + 1
    check = 0
    for r in range(reps):
        y = x * (x + r)
        check += y % m % 1000000007
        check += (y // m) % 1000000007
    return check


reps = int(sys.argv[1]) if len(sys.argv) > 1 else 200
start = time.perf_counter()
r = run(reps)
elapsed = time.perf_counter() - start
print(r)
print(elapsed)
