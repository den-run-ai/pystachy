# #615: a big live set, short-lived big strs, then many small allocations: the heap peak
import sys
import time


def main() -> None:
    t0 = time.perf_counter()
    keep = [0.5] * 16777216  # 128 MiB that stays live
    junk: list[str] = []
    for i in range(int(sys.argv[1])):
        junk.append(str(i % 10) * 1048576)  # N strs of 1 MiB, live until the loop ends
    junk = []  # garbage from here on
    k = 0
    for i in range(int(sys.argv[2])):  # then many small allocations
        k += len(str(i))
    print(len(keep), len(junk), k)
    print("TIME", time.perf_counter() - t0, file=sys.stderr)


main()
