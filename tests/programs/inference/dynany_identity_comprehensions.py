# pystachy: dynamic-any
from typing import Any


def same(a: Any, b: Any) -> bool:
    return a is b and id(a) == id(b)


def parameter_shadow(i: int) -> None:
    original: Any = i
    items: list[Any] = [i for i in [int("4000"), int("5000")]]
    print("parameter shadow", items, same(original, i), same(original, items[0]))


def run() -> None:
    xs = [int("1000"), int("1000"), int("2000")]
    print("binding", [same(i, i) for i in xs])
    items: list[Any] = [i for i in xs]
    print("iterations", same(items[0], items[1]), same(items[1], items[2]))
    fs = [float("nan"), float("-0.0"), float("0.0")]
    print("float binding", [same(i, i) for i in fs])
    i = int("3000")
    outer: Any = i
    print("shadow", [same(i, i) for i in xs], same(outer, i))
    empty: list[int] = []
    print("empty", [same(i, i) for i in empty], same(outer, i))
    print("nested", [[same(i, i) for i in xs] for i in xs], same(outer, i))
    # A later clause with the same target rebinds the comprehension's own slot.
    print("clauses", [same(i, i) for i in xs for i in xs], same(outer, i))
    print("short circuit", any(same(i, i) for i in xs), all(same(i, i) for i in xs), same(outer, i))
    print("dict", {j: same(i, i) for j, i in enumerate(xs)})
    print("set", {int(same(i, i)) for i in xs})
    # The first iterable reads the outer binding before the target hides it.
    print("iterable", [same(i, i) for i in range(i, i + 2)], same(outer, i))


run()
parameter_shadow(int("3000"))
