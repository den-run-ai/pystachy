# Generator functions (#490): lazy start, for loops, return, annotations from typing and
# collections.abc, unannotated generators (templates, one per argument types), methods and
# __iter__ written with yield, and generators that share a yield type sharing one type.
import collections.abc
import typing
from collections.abc import Generator, Iterable, Iterator


def countdown(n: int) -> Iterator[int]:
    print("countdown starts")
    while n > 0:
        yield n
        n -= 1
    print("countdown ends")


def evens(limit: int) -> Iterable[int]:
    for i in range(0, limit, 2):
        yield i


def numbered(words: list[str]) -> Generator[str, None, int]:
    k = 0
    for w in words:
        if w == "":
            return -1
        k += 1
        yield str(k) + ":" + w
    return k


def pairs(xs):
    # unannotated: what it yields is decided by each call's argument types
    for i in range(len(xs) - 1):
        yield xs[i], xs[i + 1]


def nothing() -> typing.Iterator[str]:
    return
    yield "never"


def nones() -> collections.abc.Iterator[None]:
    yield
    yield None


class Grid:
    def __init__(self, w: int, h: int) -> None:
        self.w = w
        self.h = h

    def __iter__(self) -> Iterator[tuple[int, int]]:
        for y in range(self.h):
            for x in range(self.w):
                yield (x, y)

    def diagonal(self):
        for i in range(min(self.w, self.h)):
            yield i * 10


def pick(fast: bool) -> Iterator[int]:
    # two generator functions of one yield type: one type, either generator
    return countdown(2) if fast else evens(5)


g = countdown(3)
print("made, nothing run yet")
for x in g:
    print("got", x)
for x in g:
    print("never: the generator is finished")
for e in evens(7):
    print("even", e)
for line in numbered(["a", "b"]):
    print(line)
for line in numbered(["x", "", "y"]):
    print(line)
for a, b in pairs([1, 2, 3]):
    print("pair", a, b)
for a2, b2 in pairs(["p", "q"]):
    print("pair", a2, b2)
for s in nothing():
    print("never", s)
print(list(nones()))
grid = Grid(2, 2)
for cell in grid:
    print("cell", cell)
for d in grid.diagonal():
    print("diag", d)
for fast in [True, False]:
    for v in pick(fast):
        print("picked", v)
