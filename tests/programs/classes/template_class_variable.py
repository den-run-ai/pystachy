# a class attribute of a class template that is assigned through the class (C.x = v, C.x += 1,
# cls.x = v) is the class's: the objects of every specialization that have not assigned x
# themselves read its current value, as an ordinary class's objects do (class_vars.py)
from typing import Generic, TypeVar

T = TypeVar("T")


class Style:
    default = "%"
    made = 0
    seen: list[str] = []
    scale = 1.5

    def __init__(self, fmt):
        self.fmt = fmt
        Style.made += 1
        Style.seen.append(str(fmt))

    def show(self) -> str:
        return self.default + str(self.fmt) + " " + str(self.made) + " " + str(self.scale)

    @classmethod
    def rescale(cls, by: float) -> None:
        cls.scale = by


class Box(Generic[T]):
    limit = 2
    label = "box"

    def __init__(self, item: T) -> None:
        self.item = item

    def room(self) -> int:
        return self.limit - 1


def main() -> None:
    a = Style("a")
    b = Style(1)
    print(a.show(), "|", b.show(), "|", Style.made, a.made, b.made)
    Style.default = "@"
    c = Style(2.5)
    print(a.show(), "|", b.show(), "|", c.show())
    print(a.default, b.default, c.default, Style.default)
    b.default = "own"
    Style.default = "#"
    print(a.default, b.default, c.default, Style.default, b.show())
    Style.rescale(4.0)
    print(a.scale, b.scale, c.scale, Style.scale, a.show())
    Style.seen.append("x")
    print(a.seen, b.seen is Style.seen, len(c.seen))
    Style.seen = ["new"]
    print(a.seen, b.seen, c.seen is Style.seen)
    print(hasattr(a, "default"), hasattr(b, "made"), Style.made)

    i = Box(1)
    s = Box("s")
    print(i.room(), s.room(), i.limit, s.limit, i.label, s.label)
    Box.limit = 10
    Box.label += "!"
    print(i.room(), s.room(), i.limit, s.limit, i.label, s.label, Box.limit)
    s.limit = 0
    Box.limit += 1
    print(i.room(), s.room(), i.limit, s.limit, Box.limit)


main()
