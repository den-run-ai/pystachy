from mpz import mpz
import sys
import time


def run(reps: int) -> int:
    short = "1234567890" * 12 + "12345678"
    long = "1234567890" * 100
    total = 0
    for i in range(reps):
        total += len(str(mpz(short)))
        if i % 20 == 0:
            total += len(str(mpz(long)))
    return total


reps = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
start = time.perf_counter()
r = run(reps)
elapsed = time.perf_counter() - start
print(r)
print(elapsed)
