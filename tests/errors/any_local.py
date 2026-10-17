# error: any_local.py:7: error: typing.Any is only supported in the parameter and return annotations of a function
# A local annotated with Any in another type is storage too: its items could have any type
from typing import Any


def f() -> int:
    xs: list[Any] = []
    xs.append(1)
    return len(xs)


print(f())
