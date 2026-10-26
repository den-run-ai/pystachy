
# Growing products: 3000! then its digit sum, repeated.
import sys
import time


def run(n: int, reps: int) -> int:
    check = 0
    for r in range(reps):
        f = 1
        for i in range(2, n + 1):
            f *= i
        check += f % 1000000007
    return check


reps = int(sys.argv[1]) if len(sys.argv) > 1 else 20
start = time.perf_counter()
r = run(3000, reps)
elapsed = time.perf_counter() - start
print(r)
print(elapsed)
