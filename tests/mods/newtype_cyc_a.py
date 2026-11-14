# (tests/programs/generics/newtype_cycle.py) imports newtype_cyc_b before its class statement
import mods.newtype_cyc_b


class C:
    pass
