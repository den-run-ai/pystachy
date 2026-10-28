# pystachy: python-int
# int64-range work: longest Collatz chain below a bound (no value leaves int64).
import sys
import time


def run(n: int) -> int:
    best = 0
    best_start = 0
    for start in range(1, n):
        x = start
        steps = 0
        while x != 1:
            x = x // 2 if x % 2 == 0 else 3 * x + 1
            steps += 1
        if steps > best:
            best = steps
            best_start = start
    return best * 1000000 + best_start


n = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
start = time.perf_counter()
r = run(n)
elapsed = time.perf_counter() - start
print(r)
print(elapsed)
