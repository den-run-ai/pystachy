# small objects that hold no reference (pys_new: allocelide) in a loop, some kept
import sys
import time


class Vec:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def add(self, o: "Vec") -> "Vec":
        return Vec(self.x + o.x, self.y + o.y)


def main() -> None:
    n = int(sys.argv[1])
    t0 = time.perf_counter()
    keep: list[Vec] = []
    acc = Vec(0.0, 0.0)
    for i in range(n):
        v = Vec(float(i), 1.0)
        acc = acc.add(v)
        if i % 4 == 0:
            keep.append(v)
        if len(keep) > 100000:
            keep = []
    print(acc.x, acc.y, len(keep))
    print("TIME", time.perf_counter() - t0, file=sys.stderr)


main()
