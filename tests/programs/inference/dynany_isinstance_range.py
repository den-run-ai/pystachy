# pystachy: dynamic-any
# isinstance() of an Any value with range: a boxed range is an object of the range class, as
# type() already reports it, alone, in a tuple or union of types, and as the narrowed type
from typing import Any


class Span:
    def __init__(self, n: int) -> None:
        self.n = n

    def __len__(self) -> int:
        return self.n


def is_range(x: Any) -> bool:
    return isinstance(x, range)


def kind(x: Any) -> str:
    if isinstance(x, (range, str)):
        return "range or str"
    if isinstance(x, list | tuple):
        return "list or tuple"
    if not isinstance(x, (int, range)):
        return "other"
    return "int"


def describe(x: Any) -> str:
    if isinstance(x, range):
        return f"{len(x)} {x.start} {x.stop} {x.step} {list(x)} {4 in x}"
    return "not a range: " + type(x).__name__


def total(x: Any) -> int:
    n = 0
    if isinstance(x, range) and len(x) > 1:
        for item in x:
            n += item
        n += x[1] + x[-1]
    return n


values: list[Any] = [range(1, 8, 3), range(0), range(5), [1, 2], (1, 2), "ab", None, 3, True, 2.5, Span(2), {"k": 1}]
for value in values:
    print(type(value).__name__, is_range(value), type(value) is range, kind(value), total(value))
    print(describe(value))

local: Any = range(3)
print(isinstance(local, range), isinstance(local, (list, tuple)), isinstance(local, object))
local = [0, 1, 2]
print(isinstance(local, range), isinstance(local, (list, range)))
held: dict[str, Any] = {"r": range(2), "n": 2}
print([isinstance(held[key], range) for key in held])
print([v for v in values if isinstance(v, range)])
