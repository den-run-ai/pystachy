# pystachy: dynamic-any
from typing import Any


class Number:
    def __int__(self) -> int:
        print("int method")
        return 7

    def __float__(self) -> float:
        print("float method")
        return 2.5

    def __index__(self) -> int:
        print("unused index")
        return 99


class Index:
    def __index__(self) -> int:
        print("index fallback")
        return 4


class Child(Index):
    def __index__(self) -> int:
        print("child index")
        return 5


class BadInt(Index):
    def __int__(self) -> str:
        print("bad int")
        return "12"


class BadFloat(Index):
    def __float__(self) -> int:
        print("bad float")
        return 12


class BadIndex:
    def __index__(self) -> float:
        print("bad index")
        return 1.5


class DynamicResult:
    def __init__(self, value: Any) -> None:
        self.value = value

    def __int__(self) -> Any:
        print("dynamic int")
        return self.value

    def __float__(self) -> Any:
        print("dynamic float")
        return self.value


class Raising:
    def __int__(self) -> int:
        raise ValueError("int failed")

    def __float__(self) -> float:
        raise ValueError("float failed")


class WrongArity:
    def __int__(self, extra: int) -> int:
        return extra


class BadContainer:
    def __int__(self) -> list[int]:
        print("container result")
        return [1, 2]


def convert(value: Any) -> None:
    try:
        print("int:", int(value))
    except TypeError as error:
        print("TypeError:", error)
    except ValueError as error:
        print("ValueError:", error)
    try:
        print("float:", float(value))
    except TypeError as error:
        print("TypeError:", error)
    except ValueError as error:
        print("ValueError:", error)


convert(Number())
convert(Index())
convert(Child())
convert(BadInt())
convert(BadFloat())
convert(BadIndex())
convert(DynamicResult(13))
convert(DynamicResult(1.25))
convert(DynamicResult("bad"))
convert(Raising())
convert(WrongArity())
convert(BadContainer())
convert(17)
convert(3.5)
convert("24")
convert(None)
