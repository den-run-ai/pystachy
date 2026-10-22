# pystachy: dynamic-any
# Invalid abs method signatures fail at the call, not when an unrelated value
# uses a dispatcher. The operand is evaluated first, exactly once.
from typing import Any


class MissingPos:
    def __abs__(self, extra: int) -> int:
        print("unreachable body")
        return extra


class MissingKw:
    def __abs__(self, *, extra: int) -> int:
        return extra


class Default:
    def __abs__(self, extra: int = 7) -> int:
        return extra


def operand(value: Any) -> Any:
    print("operand")
    return value


def magnitude(value: Any) -> Any:
    return abs(value)


bad: Any = MissingPos()
print(magnitude(-3))
for value in [bad, MissingKw(), Default()]:
    try:
        print(magnitude(operand(value)))
    except TypeError as error:
        print(error)
