# pystachy: dynamic-any
# Typed parameters keep the source object, including across later argument effects.
from typing import Any


def int_arg(source: Any, value: int) -> None:
    boxed: Any = value
    print("int argument", source is boxed, id(source) == id(boxed))


def float_arg(source: Any, value: float) -> None:
    boxed: Any = value
    print("float argument", source is boxed, id(source) == id(boxed))


def pair(a: int, b: int) -> None:
    left: Any = a
    right: Any = b
    print("typed pair", left == right, left is right, id(left) == id(right))


def nan_args(a: float, b: float) -> None:
    left: Any = a
    right: Any = b
    items: set[Any] = {left, right}
    keys: dict[Any, int] = {left: 1, right: 2}
    print("nan arguments", len(items), len(keys), keys[left])


G = int("1000")
old: Any = G


def change() -> int:
    global G
    G = int("1000")
    print("changed global")
    return 7


def snapshot(value: int, ignored: int) -> None:
    boxed: Any = value
    now: Any = G
    print("argument snapshot", boxed is old, boxed is now, ignored)


def fail() -> int:
    print("failing argument")
    raise ValueError("argument failure")


def run() -> None:
    n = int("1000")
    int_arg(n, n)
    alias = n
    pair(n, alias)
    pair(n, int("1000"))
    x = float("nan")
    float_arg(x, x)
    nan_args(x, x)
    nan_args(x, float("nan"))
    zero = float("-0.0")
    float_arg(zero, zero)
    snapshot(G, change())
    value = int("2000")
    original: Any = value
    int_arg(original, (value := value))
    pair(value, (value := int("2000")))
    pair(b=(value := int("2000")), a=value)
    int_arg(value=value, source=value)
    try:
        pair(value, fail())
    except ValueError as error:
        print(str(error))


run()
