# The container protocol by static dispatch: o[k] calls __getitem__, o[k] = v __setitem__, del o[k]
# __delitem__, x in o __contains__ (true as its result is; without it, x is looked for among what
# __iter__ steps through), and for loops, comprehensions, unpacking and the builtins that iterate
# step through the iterator __iter__ returns, iter() of a list, tuple, str or object; in the
# order CPython evaluates and calls them, also for a NamedTuple's and a module's class.
from collections.abc import Iterable, Iterator
from typing import NamedTuple
from mods.table import Table


def say(v: str) -> str:
    print("evaluated", v)
    return v


class Bag:
    def __init__(self) -> None:
        self.keys: list[str] = []
        self.vals: dict[str, int] = {}

    def __getitem__(self, k: str) -> int:
        print("get", k)
        return self.vals[k]

    def __setitem__(self, k: str, v: int) -> None:
        print("set", k, v)
        if k not in self.vals:
            self.keys.append(k)
        self.vals[k] = v

    def __delitem__(self, k: str) -> None:
        print("del", k)
        self.keys.remove(k)
        del self.vals[k]

    def __contains__(self, k: str) -> bool:
        print("contains", k)
        return k in self.vals

    def __iter__(self) -> Iterator[str]:
        print("iter")
        return iter(self.keys)

    def __len__(self) -> int:
        return len(self.keys)


class Grid:
    def __init__(self, w: int, h: int) -> None:
        self.w = w
        self.cells: list[int] = [0] * (w * h)

    def __getitem__(self, pos: tuple[int, int]) -> int:
        return self.cells[pos[1] * self.w + pos[0]]

    def __setitem__(self, pos: tuple[int, int], v: int) -> None:
        self.cells[pos[1] * self.w + pos[0]] = v

    def __contains__(self, v: int) -> int:
        return self.cells.count(v)

    def __iter__(self) -> "Iterator[int]":
        return iter(self.cells)


class Word:
    def __init__(self, s: str) -> None:
        self.s = s

    def __iter__(self) -> Iterable[str]:
        return iter(self.s)


class Pair:
    def __init__(self, a: int, b: int) -> None:
        self.t: tuple[int, int] = (a, b)

    def __iter__(self) -> Iterator[int]:
        return iter(self.t)


class Wrap:
    def __init__(self, g: Grid) -> None:
        self.g = g

    def __iter__(self) -> Iterator[int]:
        return iter(self.g)


class Evens:
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self) -> Iterator[int]:
        return iter([i for i in range(self.n) if i % 2 == 0])


class Stack:
    def __init__(self) -> None:
        self.items: list[list[int]] = []

    def __getitem__(self, i: int) -> list[int]:
        return self.items[i]

    def __setitem__(self, i: int, v: list[int]) -> None:
        print("stack set", i, v)
        self.items[i] = v


class Noisy:
    def __init__(self, name: str) -> None:
        self.name = name

    def __iter__(self) -> Iterator[int]:
        print("iter", self.name)
        return iter([1, 2])


def mk(name: str) -> Noisy:
    print("make", name)
    return Noisy(name)


def start() -> int:
    print("start")
    return 5


class P(NamedTuple):
    x: int
    y: int

    def __contains__(self, v: int) -> bool:
        print("P contains", v)
        return v == self.x


def total(it):
    s = 0
    for v in it:
        s += v
    return s


b = Bag()
b["x"] = 1
b[say("y")] = 2
b["z"] = 3
print(b["y"], len(b))
b[say("y")] += 10
print(b["y"])
del b[say("x")]
print("y" in b, "x" in b, "x" not in b)
for k in b:
    print("k", k)
print(list(b), sorted(b), sorted(b, reverse=True))
print([k + "!" for k in b])
print(",".join(b), max(b), min(b))
for i, k in enumerate(b):
    print(i, k)
for k, j in zip(b, [7, 8]):
    print(k, j)
p, q = b
print(p, q)
xs = ["a"]
xs.extend(b)
print(xs, any(b), all(b))

g = Grid(3, 2)
g[1, 1] = 5
g[(2, 0)] = 7
g[0, 0] += 4
print(g[1, 1], g[2, 0], g[0, 0], g.cells)
print(5 in g, 9 in g, 0 not in g)
print(list(Word("hello")), sorted(Word("cab")))
a, c = Pair(3, 4)
print(a, c, sum(Pair(5, 6)))
print([x * 2 for x in Wrap(g)])
print(list(Evens(9)))
print(1 in P(1, 2), 2 in P(1, 2))
print(3 in Pair(3, 4), 5 in Pair(3, 4))
for w in [Word("ab"), Word("cd")]:
    for ch in w:
        print(ch, end=" ")
print()
for x, y in [Pair(1, 2), Pair(3, 4)]:
    print(x + y)
print(total(g), total(Pair(1, 1)), total([1, 2]))

s = Stack()
s.items.append([1])
s[0] += [2, 3]
s[0] = []
print(s.items, s[0])

t = Table()
t["b"] = ["2"]
t["a"] = ["1", "x"]
t["a"].append("y")
print(list(t), "a" in t, "c" in t, [t[k] for k in t])

# zip() and enumerate() call __iter__ once their arguments are evaluated
for i, j in zip(mk("a"), mk("b")):
    print(i, j)
for i, j in enumerate(mk("c"), start()):
    print(i, j)
