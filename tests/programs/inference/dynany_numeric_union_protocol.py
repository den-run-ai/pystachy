# pystachy: dynamic-any
from typing import Any


class MixedInt:
    def __init__(self, valid: bool) -> None:
        self.valid = valid

    def __int__(self) -> int | list[int]:
        if self.valid:
            return 7
        return [1, 2]


class MixedFloat:
    def __init__(self, valid: bool) -> None:
        self.valid = valid

    def __float__(self) -> float | list[str]:
        if self.valid:
            return 1.25
        return ["invalid"]


class OptionalInt:
    def __init__(self, valid: bool) -> None:
        self.valid = valid

    def __index__(self) -> int | None:
        return 1 if self.valid else None


def show_int(value: Any) -> None:
    try:
        print(int(value))
    except TypeError as error:
        print(error)


def show_float(value: Any) -> None:
    try:
        print(float(value))
    except TypeError as error:
        print(error)


show_int(MixedInt(True))
show_int(MixedInt(False))
show_float(MixedFloat(True))
show_float(MixedFloat(False))
show_int(OptionalInt(True))
show_int(OptionalInt(False))
show_float(OptionalInt(True))
show_float(OptionalInt(False))
