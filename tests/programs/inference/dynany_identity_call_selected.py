# pystachy: dynamic-any
from typing import Any


def conditional(value: float, keep: bool) -> float:
    selected = value if keep else -value
    copied = selected
    return copied


def optional(value: float, keep: bool) -> float | None:
    return value if keep else None


def union(value: int, other: float, keep: bool) -> int | float:
    return value if keep else other


def either(value: float, other: float) -> float:
    return value or other


def both(value: float, other: float) -> float:
    return value and other


def fresh(value: float) -> float:
    return value and -value


def literal(keep: bool) -> int:
    return 1000 if keep else 1001


def rebound(value: float, other: float, keep: bool) -> float:
    selected = value if keep else (value := other)
    return selected


def fail() -> float:
    raise ValueError("branch")


def one_edge(value: float, keep: bool) -> float:
    return value if keep else fail()


source = float("nan")
other = float("nan")
original: Any = source
alternative: Any = other
a: Any = conditional(source, True)
b: Any = conditional(source, False)
print("conditional", a is original, b is original, len({a, original}))
c: Any = optional(source, True)
d: Any = optional(source, False)
print("optional", c is original, d is None)
number = int("1000")
integer: Any = number
e: Any = union(number, source, True)
f: Any = union(number, source, False)
print("union", e is integer, f is original)
g: Any = either(source, other)
h: Any = both(source, other)
i: Any = fresh(source)
print("boolean", g is original, h is alternative, i is original)
zero = float("-0.0")
zero_object: Any = zero
j: Any = both(zero, other)
k: Any = either(zero, source)
print("zero", j is zero_object, k is original)
first: Any = literal(True)
second: Any = literal(True)
print("literal", first is second)
left: Any = rebound(source, other, True)
right: Any = rebound(source, other, False)
print("rebind", left is original, right is alternative)
alive: Any = one_edge(source, True)
print("one edge", alive is original)
try:
    one_edge(source, False)
except ValueError as error:
    print(error)
