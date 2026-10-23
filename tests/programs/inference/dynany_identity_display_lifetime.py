# pystachy: dynamic-any
from typing import Any


def build(flag: bool) -> list[Any]:
    a = float("nan")
    b = float("nan")
    # Selecting a binding must retain the selected object before either is replaced.
    values: list[Any] = [a if flag else b, a, b, (a := float("nan")), (b := float("nan"))]
    return values


def conditional(flag: bool) -> None:
    x = int("1000")
    values: list[Any] = [x, x, (x := int("1000")) if flag else x, x]
    print("conditional", flag, values[0] is values[1], values[0] is values[2], values[2] is values[3])
    x = int("1000")
    same: list[Any] = [x, (x := x), x]
    print("self assignment", same[0] is same[1], same[1] is same[2])


def verify(flag: bool) -> None:
    values = build(flag)
    for i in range(12):
        scratch: list[Any] = [float("nan"), int("1000"), str(i)]
        if len(scratch) != 3:
            print("bad scratch")
    print("escaped", flag, values[0] is values[1], values[0] is values[2])
    print("new bindings", values[0] is values[3], values[0] is values[4])
    print("escaped ids", id(values[0]) == id(values[1]), id(values[0]) == id(values[2]))


def effects() -> None:
    x = int("1000")
    try:
        values: list[Any] = [x, x, int("bad"), (x := int("2000"))]
        print("unreachable", values)
    except ValueError:
        print("first exception", x)
    for i in range(3):
        x = int("1000")
        values = [x, x, (x := int("2000"))]
        print("loop", i, values[0] is values[1], values[0] is values[2])


def callback(flag: bool) -> None:
    x = int("1000")

    def change() -> int:
        nonlocal x
        x = int("2000")
        return 0

    values: list[Any] = [x, x, change() if flag else 0, x]
    print("callback", flag, values[0] is values[1], values[0] is values[3])
    x = int("1000")
    nested: list[Any] = [(x, x, (x := int("2000")))]
    print("nested tuple", nested[0][0] is nested[0][1], nested[0][0] is nested[0][2])


conditional(True)
conditional(False)
verify(True)
verify(False)
effects()
callback(True)
callback(False)
