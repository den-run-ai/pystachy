# error: cannot infer the type of class attribute 'KINDS'; annotate it (KINDS: T = ...)
# A generic class's attribute is typed per specialization, so it types no other class's.
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    KINDS = ["a", "b"]

    def __init__(self, value: T) -> None:
        self.value = value


class Printer:
    KINDS = Box.KINDS


print(Printer.KINDS, Box(1).value)
