
# Growing sums: Fibonacci(20000) by iteration, repeated.
import sys
import time


def run(n: int, reps: int) -> int:
    check = 0
    for r in range(reps):
        a = 0
        b = 1
        for i in range(n):
            a, b = b, a + b
        check += a % 1000000007
    return check


reps = int(sys.argv[1]) if len(sys.argv) > 1 else 20
start = time.perf_counter()
r = run(20000, reps)
elapsed = time.perf_counter() - start
print(r)
print(elapsed)
