# (tests/programs/reflection/type_alias_cycle_forms.py) imports modules whose type aliases read C
# through this module, before its class statement and after
try:
    import mods.talias_forms_nested
except AttributeError:
    print("dict[str, a.C] | None: AttributeError")
import mods.talias_forms_str


class C:
    pass


import mods.talias_forms_bound
