# pystachy: dynamic-any
# Augmented slices evaluate their bounds once but convert them for both the read
# and the later store. A list test keeps both native and boxed layouts dynamic.
from typing import Any


class Bound:
    def __init__(self, label: str, first: int, later: int) -> None:
        self.label = label
        self.first = first
        self.later = later
        self.calls = 0

    def __index__(self) -> int:
        self.calls += 1
        print("index", self.label, self.calls)
        return self.first if self.calls == 1 else self.later


def bound(label: str, first: int, later: int) -> Any:
    print("bound", label)
    return Bound(label, first, later)


def replacement() -> list[int]:
    print("replacement")
    return [70, 80]


def exercise(value: Any, first: Any) -> None:
    if isinstance(value, list):
        value[bound("start", 1, 2):bound("stop", 3, 3):bound("step", 1, 1)] += replacement()
        print("augmented", value, value[0] is first)
        value[1:2] *= 2
        print("repeat", value, value[1] is value[2])
        del value[1:3]
        print("delete", value)
        value[1:2] = []
        print("empty replacement", value)


def zero_on_store(value: Any) -> None:
    try:
        value[bound("unused start on store", 0, 0):bound("unused stop on store", 1, 1):bound("zero on store", 1, 0)] += replacement()
    except ValueError as error:
        print("store error", error, value)


def captured_receiver() -> None:
    items: list[int] = [1, 2, 3]
    value: Any = items
    other: Any = [9]

    def change() -> list[int]:
        nonlocal value
        value = other
        items.clear()
        items.extend([4, 5])
        print("changed target", items)
        return [6]

    value[0:2] += change()
    print("captured receiver", items, value, value is other)


def bad_receiver(value: Any) -> None:
    try:
        value[bound("start", 0, 0):bound("stop", 1, 1)] = replacement()
    except TypeError as error:
        print("bad receiver", error)


def bad_replacement(value: Any) -> None:
    try:
        value[:] = 42
    except TypeError as error:
        print("bad replacement", error, value)


first = int("1000")
second = int("2000")
third = int("3000")
native: list[int] = [first, second, third, 40]
print("native")
exercise(native, first)
boxed: Any = [first, second, third, 40]
print("boxed")
exercise(boxed, first)
boxed[1:1] = ["unrestricted"]
print("boxed types", boxed)
zero_on_store(native)
captured_receiver()
bad_receiver(None)
bad_replacement(native)
