# error: a set[Any] cannot become an Any value: Any values hold no sets yet (a list comprehension of its items can become one)
# pystachy: dynamic-any
# a set cannot become an Any value yet (#775), however its items are typed: the message says so
# and advises what compiles (#1591; CPython prints 2)
from typing import Any

s: set[Any] = {1, "a"}
x: Any = s
print(len(x))
