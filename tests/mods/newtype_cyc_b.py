# (tests/programs/generics/newtype_cycle.py) reads newtype_cyc_a.C, which newtype_cyc_a has not
# bound yet where it imports this module
from typing import NewType

from mods import newtype_cyc_a as a

N = NewType("N", a.C)
print("not reached")
