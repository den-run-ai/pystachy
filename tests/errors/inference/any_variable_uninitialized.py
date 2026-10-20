# error: typing.Any is only supported
from typing import Any


def f() -> int:
    value: Any
    value = 1
    return value


print(f())
