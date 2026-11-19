# error: lib_enum_int_list.py:12: error: expected int, got Color (a member of Color is held as it is by a variable, field, parameter or return annotated int, not here: use its .value)
# A list[int] display takes no IntEnum member: its items are ints, and CPython's list holds the
# member as it is (printing [<Color.RED: 1>]), which only a variable, field, parameter or return
# annotated int does here (#1394).
from enum import IntEnum


class Color(IntEnum):
    RED = 1


levels: list[int] = [Color.RED]
print(levels)
