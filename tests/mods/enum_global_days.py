# An enum class that @global_enum decorates, in a module other modules import
# (tests/programs/library/lib_enum_global.py)
from enum import IntEnum, global_enum


@global_enum
class Day(IntEnum):
    MONDAY = 0
    TUESDAY = 1


def first() -> Day:
    return MONDAY
