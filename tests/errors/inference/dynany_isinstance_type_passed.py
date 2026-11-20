# error: isinstance() of an Any value is only supported with builtin types, classes, None and tuples of them
# pystachy: dynamic-any
# a parameter named type that defaults to the builtin may be passed another function, which the
# call is then compiled with: its result is no type that this test decides (#1581; CPython prints
# True, then False)
from typing import Any


def tested(x: Any, type=type) -> bool:
    return isinstance(x, type(None))


print(tested(None))
print(tested(None, lambda v: int))
