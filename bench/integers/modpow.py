# pystachy: python-int
# RSA-sized modular exponentiation with three-argument pow.
import sys
import time


def run(reps: int) -> int:
    m = 2 ** 521 - 1
    e = 2 ** 255 + 12345
    check = 0
    for i in range(reps):
        check ^= pow(i + 3, e, m) & 0xFFFFFFFF
    return check


reps = int(sys.argv[1]) if len(sys.argv) > 1 else 300
start = time.perf_counter()
r = run(reps)
elapsed = time.perf_counter() - start
print(r)
print(elapsed)
