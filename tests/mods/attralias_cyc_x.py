# x imports y, whose alias A = cx.K (import mods.attralias_cyc_x as cx) names x's class: y
# imported first, x runs to its end before y's alias reads it (tests/programs/imports/
# import_attr_class_alias_cycle.py); x imported first, it has not run its class statement then
# (tests/deviations/circular_class_alias.py does that)
import mods.attralias_cyc_y


class K:
    def __init__(self) -> None:
        self.n = 1
