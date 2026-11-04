# pystachy: dynamic-any
# list's unbound descriptors use the same checked native boundary, including
# stored method values, and validate the receiver after evaluating arguments.
from typing import Any


def side(label: str, value: Any) -> Any:
    print("argument", label)
    return value


def fail() -> int:
    print("argument raises")
    raise ValueError("argument first")


class Pretender:
    def append(self, value: Any) -> None:
        print("wrong method", value)


class Index:
    def __init__(self, label: str, value: int) -> None:
        self.label = label
        self.value = value

    def __index__(self) -> int:
        print("index", self.label)
        return self.value


def methods(value: Any) -> None:
    if isinstance(value, list):
        list.append(value, side("append", 4))
        add = list.append
        add(value, side("stored append", 5))
        list.insert(value, 0, side("insert", 1))
        list.extend(value, (6, 7))
        order = list.sort
        order(value, reverse=side("reverse", True))
        print("methods", value)
        copied: Any = list.copy(value)
        copied.append("unrestricted")
        print("copy", copied, copied is value)


def reject(value: Any) -> None:
    try:
        list.append(side("receiver", value), side("first", 1), side("second", 2))
    except TypeError as error:
        print("rejected", error)
    try:
        list.append(value, fail())
    except ValueError as error:
        print("first error", error)


def captured_receiver() -> None:
    items: list[int] = [1]
    value: Any = items
    other: Any = [9]

    def change() -> int:
        nonlocal value
        value = other
        print("rebound receiver")
        return 2

    list.append(value, change())
    print("captured", items, value, value is other)


def index_bounds(value: Any) -> None:
    for bad in [None, 1.5, "bad"]:
        try:
            list.index(value, 2, bad, Index("must not run", 3))
        except TypeError as error:
            print("invalid start", type(bad).__name__, error)
    print("valid bounds", list.index(value, 2, Index("start", 0), Index("stop", 3)))


native: list[int] = [2, 3]
print("native")
methods(native)
print("boxed")
methods([2, 3])
reject(None)
reject(12)
reject(Pretender())
reject(native)
captured_receiver()
indices: list[int] = [1, 2, 3]
index_bounds(indices)
index_bounds([1, 2, 3])
