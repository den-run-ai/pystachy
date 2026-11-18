# pystachy: dynamic-any
# An item of a display reads a name that a later := of the display rebinds, where the name
# already holds a value of another type: the item reads that value (CPython runs the items in
# order), so the display holds values of both types. A local bound before the display, a
# parameter, and a dict display.
from typing import Any


def local() -> None:
    z: Any = "s"
    b = [1, z, (z := 2)]
    print(b, z)


def param(z: Any) -> None:
    b = [1, z, (z := 2)]
    print(b, z)


def mapping(y: Any) -> None:
    z: Any = y
    d = {"a": 1, "b": z, "c": (z := 3)}
    print(d, z)
    e = [z, "x", (z := 4.5)]
    print(e, z)


local()
param("s")
param(2.5)
mapping("str value")
mapping(None)

# Module-level code: a global bound before the display, and one that the display binds first.
g: Any = "s"
gb = [1, g, (g := 2)]
print(gb, g)
gd = {"a": (h := 2.5), "b": h, "c": (h := "t"), "d": h}
print(gd, h)
