# pystachy: dynamic-any
# Optional representation boxes are separate from a numeric value's identity companion.
from typing import Any


def same(a: Any, b: Any) -> bool:
    return a is b and id(a) == id(b)


def chosen(x: float, take: bool) -> float:
    value: float | None = None
    if take:
        value = x
    return 7.0 if value is None else value


def escaped(x: float, take: bool) -> float | None:
    value: float | None = None
    if take:
        value = x
    return value


def boxed(x: float, take: bool) -> Any:
    value: float | None = None
    if take:
        value = x
    return value


first = float("3.5")
second = float("3.5")
print(same(first, second), same(chosen(first, True), first), same(chosen(second, True), first))
for value in [first, -0.0, float("nan")]:
    print(same(chosen(value, True), value), same(escaped(value, True), value), same(boxed(value, True), value))
print(same(escaped(first, False), None), same(boxed(first, False), None))
