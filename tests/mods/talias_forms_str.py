# (tests/programs/reflection/type_alias_cycle_forms.py) names talias_forms.C, which talias_forms
# has not bound yet where it imports this module, in strings: forward references, which CPython
# does not evaluate
from typing import NewType

from mods import talias_forms as a

X = list["a.C"]
N = NewType("N", list["a.C"])
print("strings: not evaluated")
