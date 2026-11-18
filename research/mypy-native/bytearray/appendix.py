# a bytearray grown by append(), then read by index: the best of ROUNDS of each
import sys
import time


def build(n: int) -> bytearray:
    b = bytearray()
    for i in range(n):
        b.append(i & 255)
    return b


def checksum(b: bytearray) -> int:
    t = 0
    for i in range(len(b)):
        t = (t * 31 + b[i]) & 0xFFFFFFFF
    return t


def main() -> None:
    n = int(sys.argv[1])
    rounds = int(sys.argv[2])
    best_a = 1e9
    best_c = 1e9
    c = 0
    size = 0
    for _ in range(rounds):
        t0 = time.perf_counter()
        b = build(n)
        t1 = time.perf_counter()
        c = checksum(b)
        t2 = time.perf_counter()
        size = len(b)
        best_a = min(best_a, t1 - t0)
        best_c = min(best_c, t2 - t1)
    print(n, size, c, "append %.2f ms index %.2f ms" % (best_a * 1000, best_c * 1000))


main()
