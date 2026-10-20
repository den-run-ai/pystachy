# A starred unpacking evaluates its value, takes every item (an object's __iter__ once), checks
# their number, and only then evaluates and assigns each target in order, as CPython does
from typing import Iterator


def note(tag: str, v: int) -> int:
    print("eval", tag)
    return v


class Rec:
    def __setitem__(self, k: int, v: list[int]) -> None:
        print("set", k, v)


class Src:
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self) -> Iterator[int]:
        print("iter", self.n)
        return iter(list(range(self.n)))


d: dict[int, int] = {}
r = Rec()
d[note("k1", 1)], *r[note("k2", 2)], d[note("k3", 3)] = [note("a", 10), note("b", 20), note("c", 30), note("d", 40)]
print(d)
xs = [1, 2, 3]
xs[0], *ys, xs[1] = xs
print(xs, ys)
try:
    d[note("k4", 4)], *r[note("k5", 5)], d[note("k6", 6)] = Src(1)
except ValueError as e:
    print("ValueError:", e)
print(d)
d[note("k7", 7)], *r[note("k8", 8)] = Src(3)
print(d)
