# pystachy: dynamic-any
# A tuple held as an Any value repeated by zero or a negative count is the empty tuple (the
# repeat's overflow check divides by the count, which must not be 0 then).
from typing import Any

x: Any = (1, "two")
print(x * 0, x * -1, 0 * x, -3 * x, x * 1, x * 2)
e: Any = ()
print(e * 0, e * 3, len(x * 0))
s: Any = "ab"
xs: Any = [1, 2]
print(s * 0, xs * -2, s * 2, xs * 2)
# a count whose repeat would not fit: MemoryError, not a size that wraps around
one: Any = (1,)
for k in [2 ** 61, 2 ** 62, 2 ** 60 + 1]:
    try:
        print(len(one * k))
    except MemoryError:
        print("MemoryError")
