# error: any_append.py:8: error: expected int, got str (compiling add(list[int], str)
# A parameter annotated list[Any] takes its argument's type, list[int] here: a list keeps the item
# type it was made with, so appending a str to it is an error (CPython's list holds any item)
from typing import Any


def add(xs: list[Any], x: Any) -> None:
    xs.append(x)


ys = [1]
add(ys, 2)
add(ys, "s")
print(ys)
