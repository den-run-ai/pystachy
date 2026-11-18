# pystachy: dynamic-any
from typing import Any


def same(a: Any, b: Any) -> bool:
    return a is b


def observed(values: tuple[float, ...], first: Any, second: Any) -> None:
    print("items", same(values[0], first), same(values[-1], second))
    copied = list(values)
    print("list", same(copied[0], first), same(copied[-1], second))
    copied[0] = float("nan")
    print("independent", same(values[0], first), same(copied[0], first))


source: Any = float("nan")
other: Any = float("nan")
x: float = source
y: float = other
backing = [x, y, x]
values: tuple[float, ...] = tuple(backing)
backing[0] = float("nan")
observed(values, source, source)
print("search", values.count(x), values.index(x), values.index(x, 1))
print("distinct", values.count(float("nan")))
reverse = values[::-1]
joined = values[1:] + reverse[:2]
print("slice", same(reverse[0], source), same(reverse[1], other))
print("concat", same(joined[0], other), same(joined[1], source), same(joined[2], source))
print("container", tuple(values) is values, values[:] is values, values + () is values, () + values is values)
print("equal", values == reverse, values <= reverse, values >= reverse)
for item in values:
    print("iteration", same(item, source), same(item, other))
a, *middle, b = values
print("unpack", same(a, source), same(middle[0], other), same(b, source))
print("retained", same(list(reversed(values))[1], other))

# Copy before the original fresh scalar's identity has ever been observed.
fresh: tuple[float, ...] = (float("nan"), float("nan"))
sliced = fresh[1:]
concatenated = fresh + fresh
listed = list(fresh)
print("fresh", same(fresh[1], sliced[0]), same(fresh[0], concatenated[2]), same(fresh[1], listed[1]))
ints: tuple[int, ...] = (int("1000"), int("1000"))
print("int", same(ints[0], ints[0]), same(ints[0], ints[1]), same((ints + ints)[2], ints[0]))
constants: tuple[float, ...] = (1.25, -0.0, 0.0)
print("literals", same(constants[0], 1.25), same(constants[1], -0.0), same(constants[1], constants[2]))
