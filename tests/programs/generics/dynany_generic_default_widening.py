# pystachy: dynamic-any
# Hoisted defaults keep their declared scalar type across calls before a generic
# destination widens them into a union. Their original objects stay shared.
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class IntBox(Generic[T]):
    def __init__(self, value: T = 1000) -> None:
        self.value = value


class FloatBox(Generic[T]):
    def __init__(self, value: T = float("nan")) -> None:
        self.value = value


class BoolBox(Generic[T]):
    def __init__(self, value: T = False) -> None:
        self.value = value


explicit: IntBox[int | float] = IntBox(1)
first: IntBox[int | float] = IntBox()
second: IntBox[int | float] = IntBox()
left: Any = first.value
right: Any = second.value
print(explicit.value, first.value, left is right)

nan_first: FloatBox[int | float] = FloatBox()
nan_second: FloatBox[int | float] = FloatBox()
nan_left: Any = nan_first.value
nan_right: Any = nan_second.value
print(nan_left is nan_right, len({nan_left, nan_right}))

flag: BoolBox[bool | int] = BoolBox()
print(flag.value, isinstance(flag.value, bool))
