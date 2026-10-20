# error: nt_functional.py:4: error: the functional NamedTuple form is not supported: write a class, class P(NamedTuple): with annotated fields
from typing import NamedTuple

P = NamedTuple("P", [("x", int), ("y", int)])
print(P(1, 2))
