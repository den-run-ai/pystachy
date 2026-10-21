# pystachy: dynamic-any
# Ints at the 64-bit limits as Any values: boxing one tests the small-int range (pys_dyn_int),
# whose v + 5 overflowed for an int within 4 of INT64_MAX (UBSan: signed integer overflow), and
# they print, compare and add as CPython's ints do
import sys
from typing import Any


def box(n: int) -> Any:
    return n


top = sys.maxsize
for d in range(6):
    a: Any = box(top - d)
    print(a, a == top - d, a > 0, a - top)
low = -sys.maxsize - 1
for d in range(3):
    b: Any = box(low + d)
    print(b, b < 0, b - low)
edges: list[Any] = [box(-6), box(-5), box(0), box(256), box(257)]
print(edges, [e + 1 for e in edges])
