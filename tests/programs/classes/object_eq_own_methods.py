# Objects of classes that define __eq__ or __ne__ taking object, or inherit one from a base or
# their template, stored as object beside a str and an int and compared both ways: CPython calls
# the class's own method (reflected where the str or int is on the left, whose method declines),
# and for != where the class defines only __eq__, object's __ne__, which inverts it (also for a
# dataclass, an exception class and an Enum, which keep object's); object_eq_builtin_ne.py: the
# classes whose __ne__ is a builtin type's
import dataclasses
import enum


class Eq:
    def __eq__(self, other: object) -> bool:
        return isinstance(other, str)


class Ne:
    def __ne__(self, other: object) -> bool:
        return isinstance(other, str)


class Both:
    def __eq__(self, other: object) -> bool:
        return isinstance(other, str)

    def __ne__(self, other: object) -> bool:
        return isinstance(other, str)


@dataclasses.dataclass
class Point:
    x: int

    def __eq__(self, other: object) -> bool:
        return isinstance(other, str)


@dataclasses.dataclass(eq=False)
class Plain:
    x: int

    def __eq__(self, other: object) -> bool:
        return isinstance(other, int)


class Fault(Exception):
    def __eq__(self, other: object) -> bool:
        return isinstance(other, str)


class Mode(enum.Enum):
    ON = 1

    def __eq__(self, other: object) -> bool:
        return isinstance(other, int)


class Derived(Eq):
    pass


class Holder:
    def __init__(self, item):
        self.item = item

    def __eq__(self, other: object) -> bool:
        return isinstance(other, str)


def show(name: str, x: object, s: object, n: object) -> None:
    print(name, x == s, s == x, x != s, s != x, x == n, n == x, x != n, n != x)


def main() -> None:
    s: object = ""
    n: object = 5
    show("Eq", Eq(), s, n)
    show("Ne", Ne(), s, n)
    show("Both", Both(), s, n)
    show("Point", Point(1), s, n)
    show("Plain", Plain(1), s, n)
    show("Fault", Fault("f"), s, n)
    show("Mode", Mode.ON, s, n)
    show("Derived", Derived(), s, n)
    show("Holder", Holder("h"), s, n)


main()
