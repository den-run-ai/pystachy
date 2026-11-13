# error: a _ParameterKind member cannot become an Any value: an IntEnum member is an object of its class, where CPython's is also an int
# pystachy: dynamic-any
# A parameter held as an Any value does not give its kind, which would be an Any value too:
# isinstance(value, inspect.Parameter) or a typed variable gives the parameter
# (tests/programs/library/lib_inspect_any.py)
import inspect
from typing import Any

value: Any = inspect.Parameter("x", inspect.Parameter.KEYWORD_ONLY)
print(value.kind.name)
