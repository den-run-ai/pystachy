# pystachy: dynamic-any
# A number's real, imag, numerator and denominator through Any are CPython's (an int's real and a
# float's real are the number itself), and getattr()'s default is taken only for a name the
# value's type lacks, also where a class of the program defines it.
from typing import Any


class Point:
    def __init__(self) -> None:
        self.real = "field"


def parts(x: Any) -> None:
    print(type(x).__name__, x.real, x.imag, getattr(x, "real", "missing"), getattr(x, "imag", "missing"))


def ratio(x: Any) -> None:
    print(x.numerator, x.denominator, type(x.numerator).__name__, getattr(x, "denominator", "missing"))


for value in [7, -3, True, False, 2.5, -0.0]:
    parts(value)
for value in [7, -3, True, False]:
    ratio(value)
for value in [2.5, "s", [1], {"k": 1}, (1,), None, Point()]:
    print(getattr(value, "numerator", "missing"), getattr(value, "upper_case", "missing"), getattr(value, "real", "missing"))

big: Any = 1000
half: Any = 0.5
print(big.real is big, big.numerator is big, half.real is half)
try:
    print(half.numerator)
except AttributeError as error:
    print("AttributeError", error)
