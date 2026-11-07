# pystachy: dynamic-any
# Imported helpers remain lazy until a dynamic target actually needs their bodies.
from typing import Any


stable = 11


def unsupported_leaf(value: int) -> int:
    globals()
    return value + 1


def middle(value: int) -> int:
    return unsupported_leaf(value)


def deferred(value: int) -> int:
    return middle(value)


def poison(value: int) -> int:
    global stable
    stable = "unused"
    globals()
    return value


class Hidden:
    def __init__(self, pattern: str) -> None:
        self.pattern = pattern

    def __repr__(self) -> str:
        return self.pattern.format(value=3)


class Operand:
    def __init__(self, value: int) -> None:
        self.value = value

    def __add__(self, other: Any) -> int:
        return len(globals())
