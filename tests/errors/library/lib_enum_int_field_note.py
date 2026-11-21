# error: lib_enum_int_field_note.py:17: error: closed union method calls require narrowing with isinstance() first (note: what is annotated int and was given a member of Color at
# A field annotated int that is given an IntEnum member holds an int | Color, as CPython's holds
# the member (#1394): a method call on the union needs narrowing first, and the error names the
# store that widened it (CPython prints b'\x00\x01').
from enum import IntEnum


class Color(IntEnum):
    RED = 1


class P:
    def __init__(self) -> None:
        self.c: int = Color.RED

    def wide(self) -> bytes:
        return self.c.to_bytes(2, "big")


print(P().wide())
