# pystachy: dynamic-any
# hash() of a tuple that holds an Any value (CPython's Parameter.__hash__ hashes
# (name, kind, annotation, default))
from typing import Any

default: Any = 5
print(hash(("x", default)) == hash(("x", 5)))
