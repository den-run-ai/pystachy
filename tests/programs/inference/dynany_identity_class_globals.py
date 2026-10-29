# pystachy: dynamic-any
from typing import Any
from mods.dynidentity_joined_globals import Constants

original: Any = int("1000")


class Box:
    VALUE: int | float | None = original
    LITERAL = 1000
    FLOAT = 1.5
    NAN = float("nan")


class Child(Box):
    pass


class Other:
    VALUE = int("1000")


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


def replace() -> Any:
    Box.VALUE = int("1000")
    return Box.VALUE


same("class alias", original, Box.VALUE)
same("class repeated", Box.VALUE, Box.VALUE)
same("class inherited", Child.VALUE, Box.VALUE)
same("different classes", Box.VALUE, Other.VALUE)
same("class literal", Box.LITERAL, 1000)
same("class float literal", Box.FLOAT, 1.5)
same("class NaN", Box.NAN, Box.NAN)
same("class callback", Box.VALUE, replace())
same("class replacement", original, Box.VALUE)
same("inherited replacement", Child.VALUE, Box.VALUE)
Box.VALUE = float("-0.0")
saved: Any = Box.VALUE
same("class float", saved, Box.VALUE)
Box.VALUE = float("-0.0")
same("equal distinct", saved, Box.VALUE)
Box.VALUE = None
same("class None", Box.VALUE, None)
same("imported class literal", Constants.LITERAL, Constants.LITERAL)
same("imported class float", Constants.FLOAT, Constants.FLOAT)
same("different module literal", Constants.LITERAL, 1000)
same("different module float", Constants.FLOAT, 1.5)


def read_later() -> Any:
    return Later.VALUE


try:
    read_later()
except NameError:
    print("class not bound")


class Later:
    VALUE = int("2000")


same("early declaration", read_later(), Later.VALUE)


def retain() -> int:
    Box.VALUE = int("4000")
    observed: Any = Box.VALUE
    return id(observed)


before = retain()
for i in range(40):
    garbage: list[Any] = [int(str(i + 1000)), float(str(i)), "churn"]
after: Any = Box.VALUE
print("class box survives GC", before == id(after))
