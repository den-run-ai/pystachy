# pystachy: dynamic-any
# Documented deviation: copy.copy() and copy.deepcopy() of an Any value that holds an object of a
# class raise TypeError (lib/compatibility.md#copy), where CPython copies the object (here printing
# "1 True" twice): the copy of an object follows its static class, which an Any value does not
# show
import copy
from typing import Any


class P:
    def __init__(self, v: int) -> None:
        self.v = v


def deep(x: Any) -> Any:
    return copy.deepcopy(x)


def shallow(x: Any) -> Any:
    return copy.copy(x)


for f in [deep, shallow]:
    try:
        r = f(P(1))
        print(r.v, isinstance(r, P))
    except TypeError as e:
        print("TypeError:", e)
items: list[Any] = [1, [2]]
print(copy.deepcopy(items))
