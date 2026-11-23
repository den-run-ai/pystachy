# pystachy: dynamic-any
# A module that opts in to dynamic Any, storing values as object, an Any value among them
# (tests/programs/classes/object_storage_to_dynamic.py imports it)
from typing import Any

STORE: list[object] = [1, "a"]
SOME: Any = 3


def get(i: int) -> object:
    return STORE[i]


def add(v: object) -> None:
    STORE.append(v)


def held() -> object:
    x: object = SOME
    return x


def describe(o: object) -> str:
    if isinstance(o, int):
        return "int " + str(o + 1)
    if isinstance(o, str):
        return "str " + o.upper()
    return "other " + repr(o)
