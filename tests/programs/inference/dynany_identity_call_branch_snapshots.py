# pystachy: dynamic-any
# Reflection and optional keys reuse pre-evaluated arguments in sibling branches.
from typing import Callable


class Base:
    __slots__ = ("x", "_value")

    def __init__(self) -> None:
        self.x = 0
        self._value = 0

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, number: int) -> None:
        self._value = number


class Child(Base):
    __slots__ = ()


objects: list[Base] = [Base(), Child()]
for obj in objects:
    for name in ["value", "x"]:
        # Keep the name dynamic so both property and direct-field branches compile.
        setattr(obj, name + "", 5)
        print(obj.x, obj.value)
    print(getattr(*(obj, "absent", int("1000"))))


def negative(value: int) -> int:
    return -value


def extrema(key: Callable[[int], int] | None) -> None:
    print(min(3, 1, 2, key=key), max(3, 1, 2, key=key))


extrema(negative)
extrema(None)
