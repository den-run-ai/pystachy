# Iterator[T] and Iterable[T] annotations (typing's and collections.abc's, also as strings)
# type nothing, as a class template's name does: a function with such a parameter or return
# is a template, a class whose __init__ takes one is a class template, and a variable or
# field annotated so has its value's type. A Generic[T] class binds T to the items.
import collections.abc
from collections.abc import Iterable as AbcIterable
from typing import Generic, Iterable, Iterator, TypeVar

T = TypeVar("T")


def total(it: Iterable[int]) -> int:
    return sum(it)


def evens(xs: list[int]) -> Iterator[int]:
    return iter([x for x in xs if x % 2 == 0])


def first(it: "Iterator[str]") -> str:
    return next(it)


def count(it: collections.abc.Iterator[float]) -> int:
    n = 0
    for _ in it:
        n += 1
    return n


def joined(parts: AbcIterable[str], sep: str) -> str:
    return sep.join(parts)


def peek(it: Iterator[T]) -> T:
    return next(it)


class Cycle(Generic[T]):
    def __init__(self, it: Iterable[T]) -> None:
        self.it: Iterator[T] = iter(it)
        self.saved: list[T] = []
        self.i = 0

    def __iter__(self) -> Iterator[T]:
        return self

    def __next__(self) -> T:
        x = next(self.it, None)
        if x is not None:
            self.saved.append(x)
            return x
        if len(self.saved) == 0:
            raise StopIteration
        self.i += 1
        return self.saved[(self.i - 1) % len(self.saved)]


class Count:
    def __init__(self, n: int) -> None:
        self.k = 0
        self.n = n

    def __iter__(self):
        return self

    def __next__(self) -> int:
        self.k += 1
        if self.k > self.n:
            raise StopIteration
        return self.k


class Reader:
    def __init__(self, lines: Iterable[str]) -> None:
        self.lines = iter(lines)
        self.header = next(self.lines, "")

    def rows(self) -> Iterator[str]:
        return self.lines


e = evens([1, 2, 3, 4])
print(total([1, 2]), total(e), total(Count(3)), total({5: "a"}), total(iter(range(4))))
print(first(iter("xy")), list(evens([6])), count(iter([1.5, 2.5])), count(iter([0.5])))
print(joined(["a", "b"], "-"), joined(iter("cd"), "+"), joined(("é", "ü"), ""))
print(peek(iter([1])), peek(iter(["s"])), peek(Count(2)))
c = Cycle([1, 2])
print([next(c) for _ in range(5)])
d = Cycle("ab")
print(next(d), next(d), next(d))
k = Cycle(Count(2))
print(next(k), next(k), next(k), next(k))
f = Cycle(iter([4.5]))
print(next(f), next(f))
r = Reader(["h", "r1", "r2"])
none: list[str] = []
print(r.header, list(r.rows()), Reader(iter("xy")).header, Reader(none).header)
g: Iterator[int] = iter([7, 8])


def take() -> int:
    j: Iterator[int] = iter([9])
    return next(j) + next(g)


print(take(), list(g))
