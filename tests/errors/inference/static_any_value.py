# error: static_any_value.py:8: error: this module is marked '# pystachy: static', which holds no Any value: this expression is one (dict[Any,Any])
# pystachy: static
# A static module holds no Any value (docs/dynamic-any.md#static-modules): tomllib's document is
# a dict of them, so the call is rejected where it is made. Without the marker this compiles, and
# reading the document dispatches on each value's type at run time.
import tomllib

doc = tomllib.loads("n = 1")
print(len(doc))
