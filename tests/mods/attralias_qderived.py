# A class whose base is read through a module's attribute, class D(sh.Box), which
# tests/programs/imports/import_attr_class_alias_base.py aliases as derived.D
import mods.attralias_shapes as sh


class D(sh.Box):
    kind = "derived"

    def twice(self) -> int:
        return self.v * 2
