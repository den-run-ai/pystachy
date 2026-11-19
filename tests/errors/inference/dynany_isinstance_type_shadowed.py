# error: isinstance() of an Any value is only supported with builtin types, classes, None and tuples of them
# pystachy: dynamic-any
# type(None) names NoneType only where type is the builtin: a local of that name is called, and
# its result is no type that this test decides (#1581; CPython prints False, then True)
from typing import Any


def tested(x: Any) -> bool:
    type = lambda v: int
    return isinstance(x, type(None))


print(tested(None))
print(tested(3))
