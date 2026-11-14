# error: complex.__eq__() returns NotImplemented for these operands, which only a comparison of objects (==, <, ...) reads: calling it directly is not supported
# pystachy: dynamic-any
from typing import Any


def direct(value: Any, other: Any) -> None:
    print(value.__eq__(other))


direct(complex(1, 0), None)
