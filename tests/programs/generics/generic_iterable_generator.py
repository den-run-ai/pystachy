# A generator (a generator expression, or what a generator function returns) as the argument of
# a parameter annotated Iterable[T] binds T to what it yields, as a list's items do: of a generic
# function, of a generic class's __init__ and of collections.Counter (it was rejected: "it has no
# supported iterable item type")
from collections import Counter
from typing import Generic, Iterable, Iterator, TypeVar

T = TypeVar("T")


def first(items: Iterable[T]) -> T | None:
    for x in items:
        return x
    return None


def collect(items: Iterable[T]) -> list[T]:
    return [x for x in items]


def squares(n: int) -> Iterator[int]:
    for i in range(n):
        yield i * i


class Bag(Generic[T]):
    def __init__(self, items: Iterable[T]) -> None:
        self.items: list[T] = list(items)

    def size(self) -> int:
        return len(self.items)


words = ["bb", "a", "ccc", "a"]
print(first(w.upper() for w in words), first(x for x in words[:0]), first(squares(3)), first(squares(0)))
print(collect(len(w) for w in words), collect(squares(4)), collect((w, len(w)) for w in words[:2]))
b = Bag(w + "!" for w in words)
print(b.items, b.size(), Bag(squares(3)).items, Bag(x * 0.5 for x in range(3)).items)
c = Counter(ch for ch in "abracadabra" if ch != "r")
print(sorted(c.items()), c.most_common(1), Counter(len(w) for w in words), Counter(squares(3))[4])
