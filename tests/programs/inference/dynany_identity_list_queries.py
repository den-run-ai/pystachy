# pystachy: dynamic-any
from typing import Any


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


def run() -> None:
    first = float("nan")
    other = float("nan")
    xs: list[float] = [first, other, first]
    print("contains", first in xs, first not in xs)
    print("count", xs.count(first), xs.count(other))
    print("index", xs.index(first), xs.index(other))
    unknown = float("nan")
    print("different nan", unknown in xs, xs.count(unknown))
    try:
        xs.index(unknown)
    except ValueError:
        print("missing index")
    try:
        xs.remove(unknown)
    except ValueError:
        print("missing remove")
    same("min", min(xs), first)
    same("max", max(xs), first)
    ys: list[float] = [first, other, first]
    zs: list[float] = [other, first, first]
    print("equal lists", xs == ys, xs != ys)
    print("different lists", xs == zs, xs != zs)
    low: list[float] = [first, 1.0]
    high: list[float] = [first, 2.0]
    print("lexicographic", low < high, low <= high, high > low, high >= low)
    xs.remove(first)
    same("remove first", xs[0], other)
    same("remove rest", xs[1], first)
    print("remaining count", xs.count(first))
    keys: set[Any] = set()
    for item in ys:
        keys.add(item)
    print("iteration keys", len(keys))


run()
