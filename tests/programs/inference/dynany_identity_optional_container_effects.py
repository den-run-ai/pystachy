# pystachy: dynamic-any
from typing import Any


def same(a: Any, b: Any) -> bool:
    return a is b


def captures() -> None:
    value: float | None = float("nan")
    original: Any = value

    def replace() -> float | None:
        nonlocal value
        value = float("nan")
        return value

    values: list[float | None] = [value, value, replace(), value, (value := None)]
    print("list evaluation", same(values[0], original), same(values[0], values[1]),
          same(values[0], values[2]), same(values[2], values[3]), values[4] is None)
    value = float("nan")
    original = value
    items: tuple[float | None, ...] = (value, value, replace(), value, (value := None))
    print("tuple evaluation", same(items[0], original), same(items[0], items[1]),
          same(items[0], items[2]), same(items[2], items[3]), items[4] is None)


def bounds() -> None:
    needle: float | None = float("nan")
    old: Any = needle
    values: list[float | None] = [None, needle]
    items: tuple[float | None, ...] = (None, needle)

    def start() -> int:
        nonlocal needle
        needle = float("nan")
        return 0

    print("list bounds", values.index(needle, start()), same(values[1], old), same(needle, old))
    needle = old
    print("tuple bounds", items.index(needle, start()), same(items[1], old), same(needle, old))


class Query:
    def __init__(self, values: list[float | None]) -> None:
        self.values = values
        self.calls: int = 0

    def __eq__(self, other: Any) -> bool:
        self.calls += 1
        if self.calls == 1:
            self.values[1] = 9.0
            return False
        return other == 9.0


def queries() -> None:
    values: list[float | None] = [1.0, None]
    query = Query(values)
    dynamic: Any = query
    print("callback", dynamic in values, query.calls, values[1])


captures()
bounds()
queries()
