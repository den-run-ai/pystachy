# min() and max() of one iterable with default=: the default where the iterable has no item, of
# lists, tuples, sets, dicts, strs, ranges, generators, generator expressions, map() and
# iterable objects, also with key=. None as the default makes the result optional. key= and
# default= are evaluated once the iterable is in hand and before its first item is taken
import sys
from typing import Callable

n = len(sys.argv) - 1  # (2, not a constant)
xs = [3, 1, 2][: n + 1]
empty: list[int] = []
words = ["bb", "a", "ccc"]
nowords: list[str] = []
fl = [1.5, -2.0]
nofl: list[float] = []
print(max(xs, default=0), min(xs, default=0), max(empty, default=0), min(empty, default=-1), max(empty, default=None), min(xs, default=None))
print(max(words, key=len, default=""), min(nowords, key=len, default="?"), max(nowords, default=None), min(words, default=None), min(words, default="", key=len))
print(max(fl, default=0.0), min(nofl, default=0.5), max(nofl, default=None), max(fl, default=None))
print(max((x * x for x in xs), default=0), max((x for x in empty), default=7), min(map(abs, [-3, 2]), default=0), max(range(n - 2), default=-1), max(range(n + 2), default=-1))
d = {"a": 3, "b": 9}
nod: dict[str, int] = {}
print(max(d.values(), default=0), max(nod.values(), default=0), max(d, default=""), min(nod, default="none"), max(d, key=lambda k: d[k], default=""), max(nod.items(), default=("", 0)))
nos: set[int] = set()
print(max({4, 9}, default=0), min(nos, default=0), max("hello", default=""), max("", default="-"), max((5, 2), default=0), max([[1], [0, 5]], default=[]), max(empty[:0], default=n))


def longest(ws: list[str]) -> str | None:
    return max(ws, key=len, default=None)


def count(k: int):
    for i in range(k):
        yield i * 3 % 5


print(longest(words), longest(nowords), max(count(4), default=-1), max(count(0), default=-1), min(count(3), default=None), min(count(0), default=None))
best = max(empty, default=None)
top: int | None = max(xs, default=None)
print(best is None, (top or 0) + 1, max(xs, default=0) + min(empty, default=10), -min(fl, default=0.0))
if top is not None:
    print(top * 2)

log: list[str] = []


def note(tag: str, v: int) -> int:
    log.append(tag)
    return v


def source(k: int) -> list[int]:
    log.append("source")
    return list(range(k))


def items(k: int):
    log.append("start")
    for i in range(k):
        log.append("item")
        yield i


def by(tag: str) -> Callable[[int], int]:
    log.append(tag)
    return lambda x: -x


class Bag:
    def __init__(self, held: list[int]) -> None:
        self.held = held

    def __iter__(self):
        log.append("iter")
        return iter(self.held)


def show(v: int) -> None:
    print(v, log)
    log.clear()


show(max(items(2), default=note("default", -1)))
show(max(items(0), default=note("default", -1)))
show(max((note("x", x) for x in source(2)), default=note("default", -1)))
show(max([note("x", x) for x in source(2)], default=note("default", -1)))
show(max(range(note("stop", 3)), default=note("default", -1)))
show(max(map(abs, source(0)), default=note("default", -1)))
show(max(items(3), key=by("key"), default=note("default", -1)))
show(max(source(0), default=note("default", -1), key=by("key")))
show(max(Bag([4, 8]), default=note("default", -1)))
show(min(Bag([]), default=note("default", -1)))
