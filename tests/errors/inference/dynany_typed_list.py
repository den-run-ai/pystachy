# error: a list[float] cannot become an Any value: its items are typed, and Any's containers hold Any items (make it a list[Any] from the start, or copy it)
# pystachy: dynamic-any
# Native integer lists have checked Any views. Other typed element layouts stay
# rejected instead of reinterpreting their backing storage.
from typing import Any

xs = [1.0, 2.0]
v: Any = xs
v.append("three")
print(xs)
