# pystachy: dynamic-any
from typing import Any


def same(a: Any, b: Any) -> bool:
    return a is b


first: Any = float("nan")
second: Any = float("nan")
a: float | None = first
b: float | None = second
values: tuple[float | None, ...] = (a, None, b, a)
backing: list[float | None] = [a, None, b, a]
converted = tuple(backing)
backing[0] = b
print("source", same(values[0], first), same(values[2], second), values[1] is None)
print("list source", same(converted[0], first), same(backing[0], second), converted == values)
print("search", values.count(a), values.index(a), values.index(a, 1), values.count(None), values.index(None), values.count(float("nan")))
reverse = values[::-1]
joined = values[1:] + reverse[:2]
print("slice", same(reverse[0], first), same(reverse[1], second))
print("concat", joined[0] is None, same(joined[1], second), same(joined[2], first), same(joined[3], first))
listed = list(values)
listed[0] = b
print("list copy", same(listed[0], second), same(values[0], first), same(listed[-1], first))
for value in values:
    print("iteration", same(value, first), same(value, second), value is None)
x, *middle, z = values
print("unpack", same(x, first), middle[0] is None, same(middle[1], second), same(z, first))

raw: tuple[float, ...] = (first, second, first)
widened: tuple[float | None, ...] = raw
print("widen", same(widened[0], first), same(widened[1], second), same(widened[0], raw[0]))
print("widen copies", same(widened[1:][0], second), same(list(widened)[0], first))
fresh: tuple[float, ...] = (float("nan"), float("nan"))
fresh_optional: tuple[float | None, ...] = fresh
print("fresh widen", same(fresh_optional[0], fresh[0]), same(fresh_optional[1], fresh[1]), same(fresh_optional[0], fresh_optional[1]))
optional_fresh: tuple[float | None, ...] = (float("nan"), None, float("nan"))
print("fresh copy", same(optional_fresh[0], optional_fresh[:2][0]), same(optional_fresh[2], list(optional_fresh)[2]))

integer: Any = int("5000")
number: int | None = integer
ints: tuple[int | None, ...] = (number, None, number)
print("integer", same(ints[0], integer), ints[1] is None, same(ints[0], ints[-1]), same(list(ints)[0], integer))
