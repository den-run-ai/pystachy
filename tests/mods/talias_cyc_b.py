# (tests/programs/reflection/type_alias_cycle.py) reads talias_cyc_a.C in a type alias's value,
# which talias_cyc_a has not bound yet where it imports this module
from mods import talias_cyc_a as a

X = list[a.C]
print("not reached")
