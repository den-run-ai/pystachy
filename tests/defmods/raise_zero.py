# A class that Pystachy leaves uncompiled (its Iterable[int] field) whose body raises
# (tests/programs/imports/deftime_class_raises.py)
from typing import Iterable

print("raise_zero: before the class")


class Counted:
    made: int = 1 // 0
    xs: Iterable[int]


print("raise_zero: not reached")
