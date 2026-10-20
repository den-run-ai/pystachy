# A generic class that is no class template, without an __init__ of its own or a dataclass,
# makes objects that bind nothing: C[X] is C, in calls (C[int]()) and annotations, and its
# methods' parameters annotated with its type variables take each call's types (#539)
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
K = TypeVar("K")


class Box(Generic[T]):
    size = 3
    label: str = "box"

    def get(self, x: T) -> T:
        return x

    def twice(self, x: T) -> list[T]:
        return [x, x]

    def __repr__(self) -> str:
        return f"Box(size={self.size})"


class Empty(Generic[T]):
    pass


class Pair[K, V]:
    sep = ":"

    def show(self, k: K, v: V) -> str:
        return f"{k}{self.sep}{v}"


class Bare[T]:
    pass


@dataclass
class Tagged(Generic[T]):
    tag: str
    n: int = 0


@dataclass
class Doubled(Generic[T]):
    n: int

    def __init__(self, n: int) -> None:
        self.n = n * 2


def first(b: Box[T], x: T) -> T:
    return b.get(x)


def made() -> Box[str]:
    return Box[str]()


def total(b: "Late[int]") -> int:
    return b.n


class Late(Generic[T]):
    n = 7


b = Box[int]()
print(b, b.size, b.label, b.get(5), b.twice(2), Box.size, isinstance(b, Box))
p = Box()
print(p.get(1.5), p.twice("a"), Box[str]().get("s"))
q: Box[int] = Box()
r: Box[int] = Box[int]()
print(q.get(4), r.twice(1), q is not r)
boxes: list[Box[str]] = [Box[str](), Box(), made()]
print(len(boxes), [x.get(i) for i, x in enumerate(boxes)], first(Box[int](), 3), first(p, "t"))
e = Empty[int]()
print(isinstance(e, Empty), isinstance(Empty(), Empty))
pr = Pair[str, int]()
print(pr.show("k", 1), Pair().show(1.5, None), Pair.sep)
print(isinstance(Bare[int](), Bare), isinstance(Bare(), Bare))
print(Tagged[int]("t"), Tagged("u", 2))
d: Doubled[str] = Doubled(5)
print(Doubled[int](3), d)
print(total(Late[int]()), total(Late()))
