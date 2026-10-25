# pystachy: dynamic-any
# Numeric call provenance survives representation changes, cleanup and branch joins.
from typing import Any


def literal() -> int:
    return 1000


def optional_literal() -> float | None:
    return 1.5


def optional(value: float | None) -> float | None:
    return value


def union(value: int | float) -> int | float:
    return value


def inferred(value: float, empty: bool):
    if empty:
        return None
    return value


def mixed(number: int, value: float, first: bool):
    if first:
        return number
    return value


def cleanup(value: float) -> float:
    try:
        return value
    finally:
        value = float("nan")


def chosen(a: float, b: float, first: bool) -> float:
    return cleanup(a) if first else cleanup(b)


class Base:
    def keep(self, value: float) -> float:
        return value


class Derived(Base):
    def keep(self, value: float) -> float:
        return cleanup(value)


def virtual(obj: Base, value: float) -> float:
    return obj.keep(value)


class Maybe:
    def value(self, number: int) -> int | None:
        return number


class Empty(Maybe):
    def value(self, number: int) -> None:
        return None


def optional_virtual(obj: Maybe, number: int) -> Any:
    return obj.value(number)


class Trouble(Exception):
    def __init__(self, value: float) -> None:
        boxed: Any = value
        print("exception argument", boxed is original)
        super().__init__("trouble")


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


number = int("1000")
value = float("nan")
original: Any = value
same("literal return", literal(), 1000)
same("optional literal", optional_literal(), 1.5)
same("optional value", value, optional(value))
same("optional None", None, optional(None))
same("union typed", value, union(value))
same("union Any", original, union(original))
same("inferred optional", value, inferred(value, False))
same("inferred None", None, inferred(value, True))
same("inferred int", number, mixed(number, value, True))
same("inferred float", value, mixed(number, value, False))
same("finally return", value, cleanup(value))
same("conditional call", value, chosen(value, float("nan"), True))
same("base method", value, virtual(Base(), value))
same("derived method", value, virtual(Derived(), value))
same("optional virtual", number, optional_virtual(Maybe(), number))
same("None virtual", None, optional_virtual(Empty(), number))
kind = Trouble
print(str(kind(value)))
