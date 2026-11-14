# pystachy: dynamic-any
from typing import Any


def same(a: Any, b: Any) -> bool:
    return a is b


first: Any = float("nan")
second: Any = float("nan")
a: float | None = first
b: float | None = second
values: list[float | None] = [a, None, b, a]
alias = values
print("items", same(values[0], first), same(values[-1], first), same(values[2], second))
print("none", values[1] is None, None in values, values.count(None), values.index(None))
print("search", a in values, values.count(a), values.index(a), values.index(a, 1), values.count(b))
print("distinct", float("nan") in values, values.count(float("nan")))
copied = values.copy()
sliced = values[::-1]
joined = values + values
repeated = values * 2
print("copies", same(copied[0], first), same(sliced[0], first), same(joined[4], first), same(repeated[4], first))
print("equal", values == copied, values == sliced[::-1])
values[0] = b
values.append(a)
values.insert(1, a)
print("aliases", same(alias[0], second), same(copied[0], first), same(alias[1], first))
print("pop", same(values.pop(), first), same(values.pop(0), second))
values.remove(a)
print("remove", values.count(a), values.count(None), values.count(b))
values[:] = copied
values[::2] = [b, a]
print("slice store", same(values[0], second), same(values[2], first), same(copied[0], first))
values.clear()
values.append(None)
values.append(b)
values.extend(copied)
values.reverse()
print("clear refill", same(values[0], first), same(values[-2], second), values[-1] is None)
for value in copied:
    print("iteration", same(value, first), same(value, second), value is None)
x, *middle, z = copied
print("unpack", same(x, first), middle[0] is None, same(middle[1], second), same(z, first))

integer: Any = int("5000")
other_integer: Any = int("5000")
number: int | None = integer
numbers: list[int | None] = [number, None, other_integer, number]
print("integers", same(numbers[0], integer), same(numbers[0], numbers[-1]), same(numbers[0], numbers[2]))
print("integer copies", same(numbers.copy()[2], other_integer), same((numbers * 2)[4], integer))
print("int pop", same(numbers.pop(0), integer), numbers.pop(0) is None)
