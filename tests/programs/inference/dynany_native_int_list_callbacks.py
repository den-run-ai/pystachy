# pystachy: dynamic-any
# Callbacks may resize either view; extend keeps its successful prefix, whereas
# failed slice iteration does not install its collected replacement values.
from typing import Any, Iterator


def source(items: list[int]) -> Iterator[Any]:
    print("source first")
    items.append(90)
    yield 10
    print("source second", len(items))
    yield 20
    raise ValueError("source failed")


class Index:
    def __init__(self, items: list[int]) -> None:
        self.items = items

    def __index__(self) -> int:
        print("index callback")
        self.items.pop()
        self.items[0] = 11
        return -1


class Query:
    def __init__(self, items: list[int]) -> None:
        self.items = items

    def __eq__(self, other: Any) -> bool:
        print("query callback", other)
        self.items.clear()
        return False


class Cursor:
    def __init__(self) -> None:
        self.at = 0

    def __iter__(self) -> "Cursor":
        print("iterator iter")
        return self

    def __len__(self) -> int:
        print("iterator hint")
        return 2

    def __next__(self) -> int:
        if self.at == 2:
            raise StopIteration
        self.at += 1
        return 50 + self.at


class SliceSource:
    def __iter__(self) -> Cursor:
        print("source iter")
        return Cursor()

    def __len__(self) -> int:
        raise AssertionError("slice must not request the original iterable's length")


def run() -> None:
    items: list[int] = [1, 2]
    value: Any = items
    try:
        value.extend(source(items))
    except ValueError as error:
        print("extend", error, items)
    value.clear()
    items.extend([1, 2])
    try:
        value[1:2] = source(items)
    except ValueError as error:
        print("slice", error, items)
    print("index", value[Index(items)], items)

    first = int("1000")
    equal = int("1000")
    last = int("2000")
    items[:] = [first, equal, last]
    seen: list[Any] = []

    def changing(item: Any) -> Any:
        seen.append(item)
        print("sort callback", len(items), len(value))
        if len(seen) == 1:
            value.append(3000)
        return -item

    try:
        value.sort(key=changing)
    except ValueError as error:
        print("sort", error)
    print("keys", seen[0] is first, seen[1] is equal, seen[2] is last)
    print("restored", items, value[0] is last, value[1] is first, value[2] is equal)

    # Capture the method's receiver before evaluating an argument that rebinds
    # the Any variable; the write still belongs to the original native list.
    other: Any = [7]

    def argument() -> int:
        nonlocal value
        value = other
        print("argument")
        return 8

    value.append(argument())
    print("captured receiver", items, value, value is other)
    native: Any = items
    print("query mutation", Query(items) in native, items)
    items.extend([1, 2, 3])
    native[1:2] = SliceSource()
    print("slice hint", items)


run()
