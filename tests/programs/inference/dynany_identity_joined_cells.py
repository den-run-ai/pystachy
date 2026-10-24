# pystachy: dynamic-any
from typing import Any, Callable


def factory() -> tuple[Callable[[], Any], Callable[[], None]]:
    value: int | float = int("1000")

    def read() -> Any:
        return value

    def change() -> None:
        nonlocal value
        value = float("nan")

    return read, change


def snapshots() -> None:
    value: int | float = float("nan")

    def change() -> Any:
        nonlocal value
        value = int("2000")
        return value

    items: list[Any] = [value, value, change()]
    print("cell snapshot", items[0] is items[1], items[0] is items[2], items[2] is value)
    print("cell snapshot ids", id(items[0]) == id(items[1]), id(items[0]) == id(items[2]))


read, change = factory()
a = read()
b = read()
print("escaped cell", a is b, id(a) == id(b))
change()
c = read()
d = read()
print("changed cell", c is d, a is c, id(c) == id(d))
snapshots()
