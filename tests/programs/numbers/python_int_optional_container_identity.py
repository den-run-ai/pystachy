# pystachy: dynamic-any
# pystachy: python-int
from typing import Any


def same(a: Any, b: Any) -> bool:
    return a is b


small: Any = int("5000")
minimum: Any = int("-9223372036854775808")
x: int | None = small
y: int | None = minimum
values: list[int | None] = [x, None, y, x]
items: tuple[int | None, ...] = (x, None, y, x)
converted: tuple[int | None, ...] = tuple(values)
print("list", same(values[0], small), values[1] is None, same(values[2], minimum), same(values[0], values[-1]))
print("tuple", same(items[0], small), items[1] is None, same(items[2], minimum), same(items[0], items[-1]))
print("converted", same(converted[0], small), same(converted[2], minimum))
print("copies", same(values.copy()[2], minimum), same(items[::-1][1], minimum), same(list(items)[0], small))
print("mutations", same(values.pop(), small), same(values.pop(), minimum), values.pop() is None)
raw: tuple[int, ...] = (small, minimum)
widened: tuple[int | None, ...] = raw
print("widened", same(widened[0], small), same(widened[1], minimum))
