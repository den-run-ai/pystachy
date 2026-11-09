# pystachy: dynamic-any
# Runtime-sized argument packs bound by the runtime binder (runtime.c's pys_dyn_bind) report
# CPython's arity errors for functions without defaults, a method's bound self, a single given
# argument, three missing parameters and keyword-only ones, beside dyn_star_reducer_messages.py.
from typing import Any


def zero() -> int:
    return 0


def one(a: int) -> int:
    return a


def two(a: int, b: int) -> int:
    return a + b


def three(a: int, b: int, c: int) -> int:
    return a + b + c


def keyed(a: int, *, k: int) -> int:
    return a + k


class Box:
    def pair(self, a: int, b: int) -> int:
        return a + b


calls: list[Any] = [zero, one, two, three, keyed, Box().pair]
packs: list[Any] = [[], [1], [1, 2], [1, 2, 3]]
for f in calls:
    for p in packs:
        try:
            print(f(*p))
        except TypeError as error:
            print("TypeError:", error)
keywords: Any = {"k": 5}
for p in packs:
    try:
        print(calls[4](*p, **keywords))
    except TypeError as error:
        print("TypeError:", error)
