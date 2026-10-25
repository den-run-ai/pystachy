# pystachy: dynamic-any
from typing import Any, Callable


def take(value: int | float | bool | None = None) -> Any:
    return value


def optional(value: float | None = None) -> Any:
    return value


class Holder:
    def __init__(self, value: int | float | None = None) -> None:
        self.value: Any = value


print("default", take() is None, optional() is None)
print("explicit", take(None) is None, optional(None) is None)
call: Callable[[int | float | bool | None], Any] = take
print("callable", call(None) is None)
print("constructor", Holder().value is None, Holder(None).value is None)
source = float("nan")
original: Any = source
print("numeric", take(source) is original, optional(source) is original)
print("members", take(True), take(int("1000")))
