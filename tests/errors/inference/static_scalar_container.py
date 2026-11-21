# error: checked_scalar.py:28: error: this module is marked '# pystachy: static', which holds no Any value: this expression is one (Any)
# pystachy: dynamic-any
from typing import Any
from checked_scalar import mutable

value: Any = [1]
print(mutable(value))
