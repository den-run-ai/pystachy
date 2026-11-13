# pystachy: dynamic-any
# typed complex numbers in a module that compiles Any as dynamic values: no Any holds one
from typing import Any

c = 1 + 2j
print(c * 2, abs(c), c == 1 + 2j, f"{c:.1f}", [c], {c: 1}, str(c), (c, 2))
x: Any = 3
print(x + 1, c.real + x)
