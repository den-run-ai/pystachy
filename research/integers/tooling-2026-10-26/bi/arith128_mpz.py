from mpz import mpz
import sys
import time


def run(n: int) -> mpz:
    a = mpz("18446744073709551629")
    b = mpz("4294967311")
    mask = mpz("340282366920938463463374607431768211455")
    x = mpz("9223372036854775809")
    for i in range(n):
        x = ((x + a) * b) & mask
    return x


n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000000
start = time.perf_counter()
r = run(n)
elapsed = time.perf_counter() - start
print(str(r))
print(elapsed)
