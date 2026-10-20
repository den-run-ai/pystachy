# typing.Any in a function's parameter and return annotations, also within another type: what it
# annotates is left to each call, as a TypeVar's is, a parameter typed by its argument and the
# return by what the function returns (no value is boxed: each call's values keep their types)
import typing
from collections.abc import Callable, Mapping
from typing import Any, Optional
from typing import Any as Anything

import typing_extensions


def show(x: Any) -> str:
    return f"<{x}>"


def twice(x: int) -> Any:
    return x * 2


def describe(table: Mapping[str, Any]) -> list[str]:
    return [f"{k}={v}" for k, v in table.items()]


def total(xs: list[Any], start: Any = 0) -> Any:
    for x in xs:
        start += x
    return start


def pick(x: Optional[Any] = None, *, key: Any | None = None) -> str:
    return f"{x!r} {key!r}"


def first(x: Anything = "none", /) -> Anything:
    return x


def spelled(a: typing.Any, b: typing_extensions.Any, c: "list[Any]") -> "typing.Any":
    return (a, b, len(c))


def kind(x: Any) -> str:
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, int):
        return "int " + str(x + 1)
    if isinstance(x, str):
        return "str " + x.upper()
    if x is None:
        return "none"
    return "other " + repr(x)


def apply(fn: Callable[..., Any], *args: Any) -> Any:
    return fn(*args)


def count(*args: Any, **kwargs: Any) -> int:
    return len(args) + len(kwargs)


def options(**kwargs: Any) -> list[str]:
    return sorted(kwargs)


def fact(n: int) -> Any:
    if n <= 1:
        return 1
    return n * fact(n - 1)


def outer(n: int) -> int:
    def inner(x: Any) -> Any:
        return x * n

    return inner(2) + len(inner("ab"))


def neg(x: Any) -> Any:
    return -x


def log(msg: str) -> Any:
    print("log", msg)


print(show(1), show("a"), show([1, 2]), show(None), twice(21))
print(describe({"a": 1, "b": 2}), describe({"x": "y"}))
print(total([1, 2, 3]), total([0.5, 0.25], 0.0), total(["b", "c"], "a"))
print(pick(), pick(3), pick(key="k"), pick([1], key=2))
print(first(), first(9), spelled(1, "b", [1, 2]))
for v in [1, 2]:
    print(kind(v))
print(kind("a"), kind(True), kind(None), kind([1]), kind(2.5))
print(apply(len, "four"), apply(max, 3, 7), apply(show, 1.5))
print(count(), count(1, "a", k=2.0), options(b=1, a="x"), fact(5), outer(3))
print(sorted([3, 1, 2], key=neg), list(map(neg, [1, 2])), log("x"))
