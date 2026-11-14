# error: enum class Perm's __init__() is not supported: the compiler makes and looks up its members
# a flag class's pseudo-members are made at run time, where no __init__ is called
from enum import Flag


class Perm(Flag):
    R = 1
    W = 2

    def __init__(self, bit: int) -> None:
        self.bit = bit


print(Perm.R.bit)
