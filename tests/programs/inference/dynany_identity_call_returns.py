# pystachy: dynamic-any
# Returning a parameter or its alias preserves identity; arithmetic makes a new object.
from typing import Any


def keep_int(value: int) -> int:
    return value


def copy_int(value: int) -> int:
    alias = value
    return alias


def keep_float(value: float) -> float:
    return value


def from_any(value: Any) -> float:
    typed: float = value
    return typed


def recurse(value: float, count: int) -> float:
    if count == 0:
        return value
    return recurse(value, count - 1)


def computed(value: int) -> int:
    return value + 0


def selected(a: int, b: int, choose: bool) -> int:
    if choose:
        return a
    return b


def both(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


n = int("1000")
m = int("1000")
both("return parameter", n, keep_int(n))
both("return local alias", n, copy_int(n))
both("computed return", n, computed(n))
both("two computed returns", computed(n), computed(n))
both("chosen first", n, selected(n, m, True))
both("chosen second", m, selected(n, m, False))
x = float("nan")
both("float return", x, keep_float(x))
both("Any to typed return", x, from_any(x))
both("recursive return", x, recurse(x, 3))
items: set[Any] = {x, keep_float(x), from_any(x), recurse(x, 3)}
keys: dict[Any, int] = {x: 1, keep_float(x): 2, from_any(x): 3}
print("nan returned keys", len(items), len(keys), keys[x])
zero = float("-0.0")
both("signed zero return", zero, keep_float(zero))
print("signed zero value", str(keep_float(zero)))
