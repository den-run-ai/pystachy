# x imports y, whose A = cx.K (import mods.attralias_cyc_x as cx) reads x's class while x's code
# runs: in that circular import, A stays a variable, which cannot hold the class
# (tests/errors/imports/import_attr_class_alias_cycle.py)
import mods.attralias_cyc_y


class K:
    def __init__(self) -> None:
        self.n = 1
