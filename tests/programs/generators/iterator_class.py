# Iterator classes: an __iter__ that returns its own object (unannotated, -> "C", -> Self or
# -> Iterator[T]) or an object of another class with __next__, whose StopIteration ends the
# items, in loops, comprehensions, generator expressions and the builtins that take iterables.
import math
from typing import Generic, Iterator, Self, TypeVar

T = TypeVar("T")


class Count:
    def __init__(self, n: int) -> None:
        self.i = 0
        self.n = n

    def __iter__(self) -> "Count":
        print("iter", self.n)
        return self

    def __next__(self) -> int:
        if self.i >= self.n:
            print("stop", self.n)
            raise StopIteration
        self.i += 1
        return self.i


class Words:
    # unannotated: the returns decide the types
    def __init__(self, text: str) -> None:
        self.parts: list[str] = text.split()
        self.k = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.k == len(self.parts):
            raise StopIteration()
        self.k += 1
        return self.parts[self.k - 1]


class Letters:
    # a container whose __iter__ makes a new iterator object each time
    def __init__(self, s: str) -> None:
        self.s = s

    def __iter__(self) -> Iterator[str]:
        return LetterIter(self.s)


class LetterIter:
    def __init__(self, s: str) -> None:
        self.s = s
        self.at = 0

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> str:
        if self.at >= len(self.s):
            raise StopIteration
        self.at += 1
        return self.s[self.at - 1]


class Pairs:
    # items of a class, and of a tuple type
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self):
        return PairIter(self.n)


class PairIter:
    def __init__(self, n: int) -> None:
        self.n = n

    def __next__(self) -> tuple[int, str]:
        if self.n == 0:
            raise StopIteration
        self.n -= 1
        return (self.n, "abc"[self.n % 3])


class Box(Generic[T]):
    def __init__(self, items: list[T]) -> None:
        self.items = items
        self.at = 0

    def __iter__(self) -> Iterator[T]:
        return self

    def __next__(self) -> T:
        if self.at >= len(self.items):
            raise StopIteration
        self.at += 1
        return self.items[self.at - 1]


class Cells:
    # a class template: each specialization's __next__ returns its items' type
    def __init__(self, items):
        self.items = items
        self.at = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.at >= len(self.items):
            raise StopIteration
        self.at += 1
        return self.items[self.at - 1]


class Maybe:
    def __init__(self) -> None:
        self.k = 0

    def __iter__(self):
        return self

    def __next__(self) -> int | None:
        self.k += 1
        if self.k > 3:
            raise StopIteration
        return self.k if self.k != 2 else None


class Base:
    def __init__(self) -> None:
        self.n = 0

    def __iter__(self) -> "Base":
        return self

    def __next__(self) -> int:
        self.n += 1
        if self.n > 2:
            raise StopIteration
        return self.n


class Derived(Base):
    def __next__(self) -> int:
        self.n += 1
        if self.n > 3:
            raise StopIteration
        return -self.n


class Point:
    def __init__(self, x: int) -> None:
        self.x = x

    def __repr__(self) -> str:
        return f"Point({self.x})"


class Points:
    def __init__(self) -> None:
        self.ps = [Point(1), Point(2)]
        self.at = 0

    def __iter__(self):
        return self

    def __next__(self) -> Point:
        if self.at == len(self.ps):
            raise StopIteration
        self.at += 1
        return self.ps[self.at - 1]


for v in Count(3):
    print("for", v)
print([x * 2 for x in Count(2)])
print({x % 2 for x in Count(3)})
print(sum(x for x in Count(4)), max(x for x in Count(2)))
print(list(Count(2)), sorted(Count(3), reverse=True), tuple(Count(1)))
print(sum(Count(3)), sum(Count(2), 10), min(Count(3)), max(Count(3)))
print(any(Count(0)), all(Count(2)), any(x > 1 for x in Count(5)))
print(max(Count(3), key=lambda x: -x), min(Count(2), key=lambda x: x))
for i, w in enumerate(Words("tea for two")):
    print(i, w)
print(list(enumerate(Words("a b"), 1)), list(zip(Count(3), "xy")))
print(list(map(str.upper, Words("ab cd"))), list(filter(None, Words("x y"))), list(map(len, Words("abc d"))))
print(" ".join(Words("joined by spaces")))
print(list(Letters("abc")), [c + c for c in Letters("xy")])
letters = Letters("pq")
print(list(letters), list(letters))
print(list(Pairs(4)))
for k, ch in Pairs(2):
    print("pair", k, ch)
print(list(Box(["é", "ü"])), sum(Box([1.5, 2.5])), [x for x in Box([[1], [2, 3]])])
print(list(Cells(["s", "t"])), list(Cells([1, 2])), list(Cells([(1, "a")])))
print(list(Maybe()), [m for m in Maybe() if m is not None])
b: Base = Derived()
print([v for v in b], list(Base()))
print(list(Points()), [p.x for p in Points()])
a, z = Count(2)
print(a, z)
c = Count(5)
print(2 in c, next(c), 9 in c, 1 in Count(0))
print(Point(1) in Points(), "tea" in Words("for tea"), "x" not in Words("y"))
ws = Words("one two three")
print(next(ws), next(ws), next(ws), next(ws, "none"), next(ws, None))
it = iter(Letters("ok"))
print(next(it), next(it), next(it, "!"))
c2 = Count(4)
print(iter(c2) is c2)
for v in c2:
    if v == 2:
        break
print("rest", list(c2), list(c2))


def total(xs) -> int:
    t = 0
    for x in xs:
        t += x
    return t


def firsts(it):
    return [next(it), next(it)]


print(total(Count(3)), total([1, 2]), firsts(Words("a b c")), firsts(iter(Letters("uv"))))
print(math.dist(Box([0.0, 0.0]), Box([3.0, 4.0])), math.fsum(Box([0.5, 0.25])), math.prod(Box([2.0, 3.0])))
