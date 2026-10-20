# A dataclass's fields may name specializations of a generic class (Box[int], list[Box[str]]),
# which the dataclass's declaration makes: once, as the annotations elsewhere do.
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self) -> None:
        self.items: list[T] = []

    def put(self, x: T) -> "Box[T]":
        self.items.append(x)
        return self


@dataclass
class Shelf:
    name: str
    ints: Box[int]
    words: list[Box[str]]


s = Shelf("s", Box[int]().put(1), [Box[str]().put("é")])
s.ints.put(2)
b: Box[int] = s.ints
print(s.name, b.items, [w.items for w in s.words], s.ints is b)
