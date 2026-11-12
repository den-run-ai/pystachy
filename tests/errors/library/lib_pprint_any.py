# error: an Any value cannot be used as bytes
# pystachy: dynamic-any
# pprint selects what it writes by a value's static type, and an Any value has none.
import pprint
from typing import Any

x: Any = {"b": [1, "two"]}
print(pprint.pformat(x))
