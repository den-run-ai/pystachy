# error: checked_scalar.py:24: error: this module is marked '# pystachy: static', which holds no Any value: this expression is one (Any)
# pystachy: dynamic-any
from typing import Any
from checked_scalar import unchecked_failure

value: Any = 1
print(unchecked_failure(value))
