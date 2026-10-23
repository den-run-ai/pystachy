# pystachy: dynamic-any
# A dynamic abs call observes inherited/overridden methods, their effects,
# arbitrary results and exceptions; it evaluates its argument exactly once.
from typing import Any


class Number:
    def __init__(self, value: int):
        self.value = value

    def __abs__(self) -> int:
        print("base", self.value)
        return abs(self.value)


class Inherited(Number):
    pass


class Override(Number):
    def __abs__(self) -> int:
        print("override", self.value)
        return 42


class Label:
    def __abs__(self) -> str:
        print("label")
        return "absolute"


class Same:
    def __abs__(self) -> "Same":
        return self


class Failed:
    def __abs__(self) -> int:
        print("raising")
        raise ValueError("absolute failure")


class Missing:
    pass


def argument(value: Any) -> Any:
    print("argument")
    return value


for value in [Number(-4), Inherited(-7), Override(-9), Label(), Failed(), Missing()]:
    try:
        print(abs(argument(value)))
    except (TypeError, ValueError) as error:
        print(error)

same: Any = Same()
print(abs(same) is same)
print(abs(Number(-12)))
