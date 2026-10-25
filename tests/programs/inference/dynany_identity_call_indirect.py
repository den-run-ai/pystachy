# pystachy: dynamic-any
from typing import Any, Callable


def keep(value: float) -> float:
    return value


def apply(fn: Callable[[float], float], value: float) -> float:
    return fn(value)


class Identity:
    def keep(self, value: float) -> float:
        return value


def captured() -> Callable[[float], float]:
    offset = 0

    def inner(value: float) -> float:
        if offset == 0:
            return value
        return value + offset

    return inner


value = float("nan")
original: Any = value
fn: Callable[[float], float] = keep
method: Callable[[float], float] = Identity().keep
closure = captured()
dynamic: Any = keep
a: Any = fn(value)
b: Any = method(value)
c: Any = closure(value)
d: Any = apply(fn, value)
e: Any = dynamic(value)
print("indirect identity", a is value, b is value, c is value, d is value, e is value)
print("indirect ids", id(a) == id(original), id(b) == id(original), id(c) == id(original))
items: set[Any] = {value, a, b, c, d, e}
print("indirect nan keys", len(items))
