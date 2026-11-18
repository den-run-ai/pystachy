# error: auto() in a flag class that @_simple_enum makes is not supported (CPython 3.13's raises AttributeError)
# CPython 3.13's _simple_enum reads auto.value of the auto class for a flag: AttributeError,
# where the decorator runs
from enum import Flag, auto, _simple_enum


@_simple_enum(Flag)
class Perm:
    R = auto()


print(Perm.R)
