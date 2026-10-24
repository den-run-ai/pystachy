# pystachy: dynamic-any
# Inferred dynamic storage must capture preceding reads before later rebinding.
from typing import Any


def local_reads() -> None:
    x = int("1000")
    marker: list[Any] = ["marker"]
    items = [x, *marker, x, (x := int("1000"))]
    print("star list", items[0] is items[2], items[0] is items[3], items[3] is x)
    print("star ids", id(items[0]) == id(items[2]), id(items[0]) == id(items[3]))
    y = float("nan")
    tup = (y, *marker, y, (y := float("nan")))
    print("star tuple", tup[0] is tup[2], tup[0] is tup[3], tup[3] is y)
    empty: list[Any] = []
    z = float("-0.0")
    zeros = [z, *empty, z, (z := float("0.0"))]
    print("empty star", zeros[0] is zeros[1], zeros[0] is zeros[2], zeros)
    x = int("1000")
    late = [x, x, (x := int("2000")), *marker]
    print("late star", late[0] is late[1], late[0] is late[2], late[2] is x)
    x = int("1000")
    nested = [[x, *marker, x, (x := int("2000"))], *marker]
    inner: Any = nested[0]
    print("nested star", inner[0] is inner[2], inner[0] is inner[3])
    first = [(new := int("1000")), new, (new := int("2000")), *marker]
    print("first binding", first[0] is first[1], first[0] is first[2], first[2] is new)
    typed = [(number := int("1000")), *[2], number]
    print("typed first binding", typed)


def callbacks() -> None:
    value = int("1000")

    def change() -> list[Any]:
        nonlocal value
        print("expand")
        value = int("1000")
        return ["marker"]

    items = [value, value, *change(), value, value]
    print("star callback", items[0] is items[1], items[0] is items[3], items[3] is items[4])


def first_error() -> None:
    value = int("1000")
    marker: list[Any] = []

    def fail() -> int:
        print("first")
        raise ValueError("stop")

    def later() -> int:
        print("unreachable")
        return 0

    try:
        items = [value, *marker, value, fail(), later()]
        print(items)
    except ValueError as error:
        print(error)


local_reads()
callbacks()
first_error()
