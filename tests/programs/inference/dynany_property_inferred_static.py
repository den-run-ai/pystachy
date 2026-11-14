# pystachy: dynamic-any
# An Any value reads the inferred getters of a class from a module that does not opt in.
from typing import Any

from property_inferred_support.shapes import Shape

things: list[Any] = [Shape(2), 5, "x", Shape(3)]
for t in things:
    if isinstance(t, Shape):
        print(t.area, t.name)
    else:
        print(t)
x: Any = Shape(4)
print(x.area + 1, x.name.upper(), getattr(x, "area"))
d: dict[str, Any] = {"s": Shape(5)}
print(d["s"].area)
