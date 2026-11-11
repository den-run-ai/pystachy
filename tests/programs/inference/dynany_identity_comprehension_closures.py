# pystachy: dynamic-any
from typing import Any, Callable


def readers(values: list[int]) -> list[Callable[[], int]]:
    return [lambda: value for value in values]


def same(a: Any, b: Any) -> bool:
    return a is b and id(a) == id(b)


def run() -> None:
    first = readers([int("1000"), int("2000")])
    second = readers([int("1000"), int("2000")])
    captured: Any = first[0]()
    print("escaped", captured, same(captured, first[1]()), same(captured, second[0]()))
    value = int("3000")
    outer: Any = value
    read_outer = lambda: value
    inner = [lambda: value for value in [int("4000"), int("5000")]]
    print("shadow", same(outer, read_outer()), inner[0](), same(inner[0](), inner[1]()))
    value = int("6000")
    print("rebound", read_outer(), same(outer, read_outer()), inner[0]())
    fs = [lambda: value for value in [float("1.25"), float("2.5")]]
    print("float", fs[0](), same(fs[0](), fs[1]()))


run()
module_readers = [lambda: value for value in [int("7000"), int("8000")]]
print("module", module_readers[0](), same(module_readers[0](), module_readers[1]()))
