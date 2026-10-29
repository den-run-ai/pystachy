from mpz import mpz
import sys
import time


def modpow(b: mpz, e: mpz, m: mpz) -> mpz:
    r = mpz(1)
    b = b % m
    while e:
        if e & 1:
            r = r * b % m
        e = e >> 1
        if e:
            b = b * b % m
    return r


def run(reps: int) -> mpz:
    m = (mpz(1) << 521) - 1
    e = (mpz(1) << 255) + 12345
    check = mpz(0)
    for i in range(reps):
        check = check ^ (modpow(mpz(i + 3), e, m) & 0xFFFFFFFF)
    return check


reps = int(sys.argv[1]) if len(sys.argv) > 1 else 300
start = time.perf_counter()
r = run(reps)
elapsed = time.perf_counter() - start
print(str(r))
print(elapsed)
