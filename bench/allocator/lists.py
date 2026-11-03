# containers: lists of ints and of lists, dicts of strs, growing and dying (medium/large backings)
import sys
import time


def main() -> None:
    reps = int(sys.argv[1])
    t0 = time.perf_counter()
    total = 0
    for r in range(reps):
        a = [i * r for i in range(3000)]
        b = [[i, i + 1] for i in range(500)]
        d: dict[str, int] = {}
        for i in range(400):
            d[str(i + r)] = i
        c = a[100:2900]
        c.sort(reverse=True)
        total += c[0] + len(b) + len(d) + sum(x[1] for x in b[:10])
    print(total)
    print("TIME", time.perf_counter() - t0, file=sys.stderr)


main()
