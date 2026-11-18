# error: invalid Flag 'Bizarre': aliases b and d are missing combined values of 0x3 [use enum.show_flag_values(value) for details]
# CPython's ValueError where @verify(NAMED_FLAGS) runs: b and d have bits that no member names
from enum import NAMED_FLAGS, Flag, verify


@verify(NAMED_FLAGS)
class Bizarre(Flag):
    b = 3
    c = 4
    d = 6


print(list(Bizarre))
