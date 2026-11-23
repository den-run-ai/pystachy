# class variables of a generic class whose specializations annotations name where the classes
# are declared (a dataclass's field, a parameter, a result), before any code is compiled: their
# objects read the class's current value too (template_class_variable.py: specializations that
# calls make)
import dataclasses
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    limit = 2
    tags: list[str] = []
    name = "box"

    def __init__(self, item: T) -> None:
        self.item = item

    def room(self) -> int:
        return self.limit - 1

    @classmethod
    def rename(cls, to: str) -> None:
        cls.name = to


@dataclasses.dataclass
class Holder:
    b: Box[int]
    c: Box[str]


def total(xs: list[Box[float]]) -> int:
    return sum([x.limit for x in xs])


def first(xs: list[Box[bytes]]) -> Box[bytes]:
    return xs[0]


def main() -> None:
    h = Holder(Box(1), Box("s"))
    f = [Box(1.5), Box(2.5)]
    y = first([Box(b"y")])
    print(h.b.limit, h.c.limit, total(f), y.limit, h.b.room(), y.room(), h.c.name)
    Box.limit = 10
    Box.tags.append("t")
    Box.rename("crate")
    print(h.b.limit, h.c.limit, total(f), y.limit, h.b.room(), y.room(), h.c.tags, y.tags is Box.tags)
    print(h.b.name, h.c.name, y.name, f[0].name, Box.name)
    h.b.limit = 0
    y.name = "own"
    Box.limit += 5
    Box.rename("case")
    print(h.b.limit, h.c.limit, total(f), y.limit, Box.limit, h.b.name, y.name, Box.name)


main()
