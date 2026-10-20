# pystachy: dynamic-any
# Storage that holds None before an Any value. A local becomes dynamic from its first store, so
# that its None is an Any value's box of None also where the loop that gives it its Any value
# never runs. A module variable, a container of None items, a field that code outside its class's
# methods gives an Any value and a generator's local that are given an Any value later are annotated
# Any (unannotated, they are rejected: tests/errors/dynany_none_*).
from typing import Any


def get(i: int) -> Any:
    return [1, "s", None, 2.5][i]


def last_of(n: int):
    last = None
    for i in range(n):
        last = get(i)
    return last


def first_some(n: int):
    found = None
    for i in range(n):
        if found is None:
            found = get(i)
    print(found is None, type(found).__name__)
    return found


def none_or(k: int):
    if k == 0:
        return None
    return get(k)


print(last_of(0), last_of(2), last_of(4))
print(first_some(0), first_some(3))
print(none_or(0), none_or(1), none_or(2))
g: Any = None


def setg(i: int) -> None:
    global g
    g = get(i)


print(g)
setg(1)
print(g)
xs: list[Any] = [None] * 3
xs[0] = get(0)
xs.append(get(3))
print(xs, xs.count(None))
d: dict[str, Any] = {"a": None, "b": None}
d["a"] = get(1)
print(d)


class Box:
    def __init__(self) -> None:
        self.v: Any = None


b = Box()
print(b.v is None)


def fill(x, i):
    x.v = get(i)


fill(b, 1)
print(b.v, b.v is None, Box().v is None)


def gen(n: int):
    last: Any = None
    for i in range(n):
        last = get(i)
        yield last
    yield last


print(list(gen(0)), list(gen(2)))
