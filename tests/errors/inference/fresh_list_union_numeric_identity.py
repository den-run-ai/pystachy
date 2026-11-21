# error: expected int, got str
# pystachy: dynamic-any
from typing import Any


def same(a: Any, b: Any) -> bool:
    return a is b


def build(n: int):
    items = []
    items.append(n)
    items.append("tag")
    value = items[0]
    if isinstance(value, int):
        print(same(n, value))


build(int("1000"))
