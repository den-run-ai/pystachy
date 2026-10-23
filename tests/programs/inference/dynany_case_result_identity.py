# pystachy: dynamic-any
"""Separate case-mapping calls create distinct results, even for one byte."""
from typing import Any


def strings(value: str) -> None:
    left: Any = value.lower()
    right: Any = value.lower()
    print("lower", left == right, left is right, id(left) == id(right))
    left = value.upper()
    right = value.upper()
    print("upper", left == right, left is right, id(left) == id(right))
    left = value.swapcase()
    right = value.swapcase()
    print("swapcase", left == right, left is right, id(left) == id(right))
    left = value.casefold()
    right = value.casefold()
    print("casefold", left == right, left is right, id(left) == id(right))


for text in ["a", "A", "!"]:
    strings(text)
