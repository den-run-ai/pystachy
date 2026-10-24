# pystachy: dynamic-any
from typing import Any


class Box:
    def __init__(self) -> None:
        self.n: int = int("1000")
        self.f: float = float("nan")
        self.joined: int | float | None = None


class Maybe:
    def __init__(self, make: bool) -> None:
        if make:
            self.n = int("1000")


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


def rebind(o: Box) -> Any:
    o.n = int("1000")
    return o.n


def run() -> None:
    o = Box()
    same("repeated int", o.n, o.n)
    same("repeated nan", o.f, o.f)
    ns: set[Any] = {o.f, o.f}
    print("nan keys", len(ns))
    read: Any = getattr(o, "f", None)
    again: Any = getattr(o, "f", None)
    same("getattr default", read, o.f)
    same("getattr repeat", read, again)
    reflect_keys: set[Any] = {o.f, read, again}
    print("getattr nan keys", len(reflect_keys))
    original: Any = int("1000")
    o.n = original
    same("Any store", original, o.n)
    o.n = o.n
    same("self store", original, o.n)
    same("before callback", o.n, rebind(o))
    same("after callback", original, o.n)
    o.n = original
    copy = Box()
    copy.n = o.n
    o.n = int("1000")
    same("copied field", original, copy.n)
    same("equal replacement", copy.n, o.n)
    x: Any = float("nan")
    o.joined = x
    same("joined float", x, o.joined)
    o.joined = None
    print("joined None", o.joined is None)
    o.joined = original
    same("joined int", original, o.joined)
    z: Any = float("-0.0")
    o.f = z
    same("negative zero", z, o.f)
    o.f = float("0.0")
    same("zero replacement", z, o.f)
    # Only the field retains this computed object's box during later allocations.
    kept: Any = float("nan")
    o.f = kept
    before = id(kept)
    kept = None
    for i in range(40):
        trash: Any = float(str(i))
    after: Any = o.f
    print("field roots", before == id(after))
    optional = Maybe(False)
    try:
        same("missing", optional.n, optional.n)
    except AttributeError:
        print("missing first")
    default = int("1000")
    same("getattr missing", getattr(optional, "n", default), default)
    same("getattr None", getattr(optional, "n", None), None)
    optional.n = int("1000")
    same("late field", optional.n, optional.n)
    same("getattr assigned", getattr(optional, "n", default), optional.n)


run()
