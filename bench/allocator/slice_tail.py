# #127: s[1:] of a string of SIZE + 1 bytes, until TOTAL bytes are copied (large atomic objects)
import sys
import time


def main() -> None:
    size = int(sys.argv[1])
    total = int(sys.argv[2])
    s = "x" * (size + 1)
    n = total // size
    t = 0
    t0 = time.perf_counter()
    for i in range(n):
        u = s[1:]
        t += len(u)
    print(size, n, t)
    print("TIME", time.perf_counter() - t0, file=sys.stderr)


main()
