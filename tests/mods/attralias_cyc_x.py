# x imports y, whose alias A = x.K names x's class: imported first, x has not run its class
# statement when y's alias reads it (tests/deviations/circular_class_alias.py does that); y
# imported first, x runs to its end before y's alias (tests/programs/imports/
# import_attr_class_alias_cycle.py)
import mods.attralias_cyc_y


class K:
    def __init__(self) -> None:
        self.n = 1
