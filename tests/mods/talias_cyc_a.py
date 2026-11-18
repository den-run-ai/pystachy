# (tests/programs/reflection/type_alias_cycle.py) imports talias_cyc_b before its class statement
import mods.talias_cyc_b as b


class C:
    pass


x: b.X = [C()]
print(len(x))
