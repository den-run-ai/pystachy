from mpz import mpz
import sys
import time


def power(b: mpz, e: int) -> mpz:
    r = mpz(1)
    while e:
        if e & 1:
            r = r * b
        e >>= 1
        if e:
            b = b * b
    return r


def run(reps: int) -> mpz:
    x = power(mpz(3), 12000)
    m = power(mpz(7), 3000) + 1
    check = mpz(0)
    for r in range(reps):
        y = x * (x + r)
        check = check + y % m % 1000000007
        check = check + (y // m) % 1000000007
    return check


reps = int(sys.argv[1]) if len(sys.argv) > 1 else 200
start = time.perf_counter()
r = run(reps)
elapsed = time.perf_counter() - start
print(str(r))
print(elapsed)
