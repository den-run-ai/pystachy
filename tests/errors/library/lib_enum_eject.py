# error: flag class Space's boundary=EJECT is not supported: CPython's class then gives an int, no member
# CPython's lookup of a value with bits no member has returns the int itself (printing 7 <class 'int'>)
from enum import EJECT, Flag


class Space(Flag, boundary=EJECT):
    ONE = 1
    TWO = 2
    EIGHT = 8


print(Space(7), type(Space(7)))
