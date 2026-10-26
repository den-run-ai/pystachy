# int64-range work: a masked 31-bit LCG and xorshift mix; no value leaves int64.
import sys
import time


def run(n: int) -> int:
    x = 12345
    acc = 0
    for i in range(n):
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        acc ^= (x << 7) ^ (x >> 3)
        acc = acc & 0xFFFFFFFF
    return acc


n = int(sys.argv[1]) if len(sys.argv) > 1 else 3000000
start = time.perf_counter()
r = run(n)
elapsed = time.perf_counter() - start
print(r)
print(elapsed)
