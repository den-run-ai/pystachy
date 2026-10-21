# a template that dispatches on an object parameter with isinstance(), hasattr() or "is None":
# an argument known not to be None (a new object, self) decides the test when it compiles, so
# only the branch that runs is compiled, as for the builtin types
from typing import Iterator


class C:
    def __init__(self) -> None:
        self.xs = [1, 2]

    def __iter__(self) -> Iterator[int]:
        return iter(self.xs)

    def again(self) -> list[int]:
        return as_list(self)


class D:
    def __init__(self) -> None:
        self.v = 5


def inc(o):
    if isinstance(o, C):
        return 1
    return o + 1


def as_list(o):
    if isinstance(o, C):
        return list(o)
    else:
        return [o]


def total(o):
    if hasattr(o, "__iter__"):
        return sum(o)
    return o.v


def size(o):
    if o is None:
        return len(o)
    return 2


print(inc(C()), inc(4), as_list(C()), as_list(3), total(C()), total(D()), size(C()), C().again())
