# pystachy: dynamic-any
# Even all-int boxed items cannot prove a list's native storage layout. CPython
# ignores the annotation and prints the original list.
from typing import Any

value: Any = [1, 2]
try:
    items: list[int] = value
    print(items)
except TypeError:
    print("boxed list cannot alias native storage")
