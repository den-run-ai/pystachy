# (tests/programs/reflection/type_alias_cycle_forms.py) reads talias_forms.C, which talias_forms
# has not bound yet where it imports this module, inside a TypeAlias's value
from typing import TypeAlias

import mods.talias_forms as a

X: TypeAlias = dict[str, a.C] | None
print("not reached")
