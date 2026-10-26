from mpz import mpz
import sys
import time


def run(n: int, reps: int) -> mpz:
    check = mpz(0)
    for r in range(reps):
        f = mpz(1)
        for i in range(2, n + 1):
            f = f * i
        check = check + f % 1000000007
    return check


reps = int(sys.argv[1]) if len(sys.argv) > 1 else 20
start = time.perf_counter()
r = run(3000, reps)
elapsed = time.perf_counter() - start
print(str(r))
print(elapsed)
