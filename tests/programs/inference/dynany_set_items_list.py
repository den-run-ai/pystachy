# pystachy: dynamic-any
# a set cannot become an Any value yet (#775); a list comprehension of its items can, whatever
# their type, as the diagnostic advises (#1591)
from typing import Any

s: set[Any] = {1, "a"}
f: frozenset[int] = frozenset([3, 1, 2])
t: set[str] = {"q", "p"}
x: Any = [v for v in s]
y: Any = [v for v in f]
z: Any = [v for v in t]
print(len(x), len(y), len(z), 1 in x, "a" in x, 2 in y, "p" in z, "r" in z)
