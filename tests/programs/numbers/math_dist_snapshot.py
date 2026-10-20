# math.dist(p, q) makes tuple(p) before it iterates q: a q.__iter__ that changes the list p is,
# or the list p's own __iter__ steps through, does not change the distance (but does change
# the list). Each point's items are read as they were when it was iterated.
from math import dist
from typing import Iterator


class Mutator:
    # sets target[0], appends to it or clears it, then steps through xs
    def __init__(self, target: list[float], xs: list[float], how: str) -> None:
        self.target = target
        self.xs = xs
        self.how = how

    def __iter__(self) -> Iterator[float]:
        if self.how == "set":
            self.target[0] = 100.0
        elif self.how == "append":
            self.target.append(5.0)
        else:
            self.target.clear()
        return iter(self.xs)


class IntMutator:
    def __init__(self, target: list[int], xs: list[int]) -> None:
        self.target = target
        self.xs = xs

    def __iter__(self) -> Iterator[int]:
        self.target[0] = 100
        return iter(self.xs)


class Path:
    def __init__(self, xs: list[float]) -> None:
        self.xs = xs

    def __iter__(self) -> Iterator[float]:
        return iter(self.xs)


class Grow:
    # each __iter__ adds a coordinate first
    def __init__(self) -> None:
        self.xs = [1.0]

    def __iter__(self) -> Iterator[float]:
        self.xs.append(2.0)
        return iter(self.xs)


def maybe(xs: list[float], n: int) -> list[float] | None:
    return xs if n > 0 else None


p = [3.0]
print(dist(p, Mutator(p, [1.0], "set")), p)
p = [1.0, 2.0]
print(dist(p, Mutator(p, [0.0, 0.0], "append")), p)
p = [3.0, 4.0]
print(dist(p, Mutator(p, [0.0, 0.0], "clear")), p)
ip = [3, 4]
print(dist(ip, IntMutator(ip, [0, 0])), ip)
bp = [True, False]
print(dist(bp, Mutator([0.0], [0.0, 0.0], "set")))
path = Path([6.0, 8.0])
print(dist(path, Mutator(path.xs, [0.0, 0.0], "set")), path.xs)
mp = [2.0]
print(dist(maybe(mp, 1), Mutator(mp, [1.0], "set")), mp)
g = Grow()
try:
    print(dist(g, g))
except ValueError as err:
    print("ValueError:", err, g.xs)
g = Grow()
print(dist(g, [0.0, 0.0]), dist([0.0, 0.0, 0.0], g), g.xs)
# q is iterated after p, and changing q's list in p's __iter__ is seen
q = [9.0]
print(dist(Mutator(q, [1.0], "set"), q), q)
