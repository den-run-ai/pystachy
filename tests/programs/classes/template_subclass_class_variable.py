# a class variable of a class template (C.x = v) read through objects of the classes that
# derive from its specializations: a subclass without an __init__, one with an annotated
# __init__, one whose own __init__ is a template, and a subclass that binds the attribute again
from typing import Generic, TypeVar

T = TypeVar("T")


class Style:
    default = "%"
    made = 0
    names: list[str] = []

    def __init__(self, fmt):
        self.fmt = fmt
        Style.made += 1
        Style.names.append(str(fmt))

    def show(self) -> str:
        return self.default + str(self.fmt) + "/" + type(self).__name__ + "/" + str(self.made)

    @classmethod
    def reset(cls, to: str) -> None:
        cls.default = to


class Sub(Style):
    pass


class Fixed(Style):
    def __init__(self, n: int) -> None:
        super().__init__(n)
        self.n = n


class Loud(Style):
    default = "!"


class Deep(Style):
    def __init__(self, fmt, extra):
        super().__init__(fmt)
        self.extra = extra


class Deeper(Deep):
    default = "#"


class Box(Generic[T]):
    limit = 2

    def __init__(self, item: T) -> None:
        self.item = item

    def room(self) -> int:
        return self.limit - 1


class IntBox(Box[int]):
    pass


def shows(xs: list[Style]) -> str:
    return " ".join([x.show() for x in xs])


def main() -> None:
    a = Style("a")
    b = Sub(1)
    f = Fixed(7)
    c = Loud(2.5)
    d = Deep("d", 3)
    e = Deeper(4, "x")
    print(a.show(), b.show(), f.show(), c.show(), d.show(), e.show())
    print(a.default, b.default, f.default, c.default, d.default, e.default, b.names is Style.names)
    Style.default = "@"
    print(a.show(), b.show(), f.show(), c.show(), d.show(), e.show())
    print(a.default, b.default, f.default, c.default, d.default, e.default, Style.default)
    b.default = "own"
    Style.reset("&")
    print(a.default, b.default, f.default, c.default, d.default, e.default, Sub.default, Loud.default)
    ints = [Style(1), Sub(2), Fixed(3)]
    print(shows(ints), len(Style.names), f.made, e.made)

    i = IntBox(5)
    j = Box(6)
    s = Box("s")
    print(i.room(), j.room(), s.room(), i.limit, IntBox.limit)
    Box.limit = 10
    print(i.room(), j.room(), s.room(), i.limit, IntBox.limit)


main()
