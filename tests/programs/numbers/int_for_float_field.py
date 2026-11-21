# A constructor's float parameter types the field it fills. Given an int, the field holds an
# int | float, as if annotated so, and the object keeps the int, as CPython's does (#711, #1534)
from dataclasses import dataclass


@dataclass
class Vec:
    x: float
    y: float


print(Vec(0, 1.5))
