# error: a list[int] cannot become an Any value: its items are typed, and Any's containers hold Any items (make it a list[Any] from the start, or copy it)
# pystachy: dynamic-any
# An Any alias of a typed list would store boxes where the list's typed code reads ints (and
# its items, which the collector does not scan): rejected where the list becomes an Any value.
from typing import Any

xs = [1, 2]
v: Any = xs
v.append("three")
print(xs)
