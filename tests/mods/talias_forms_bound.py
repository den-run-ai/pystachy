# (tests/programs/reflection/type_alias_cycle_forms.py) reads talias_forms.C, which talias_forms
# has bound where it imports this module
from mods import talias_forms as a

X = list[a.C]
x: X = [a.C(), a.C()]
print("bound:", len(x))
