# pystachy: dynamic-any
# type(None) names NoneType where a local named type holds the builtin, as a parameter that
# defaults to it does (#1581): the test is the one the builtin's own name compiles to, alone and
# in a tuple of types
from typing import Any


def tested(x: Any, type=type) -> bool:
    return isinstance(x, type(None))


def either(x: Any, type=type) -> bool:
    return isinstance(x, (int, type(None)))


def builtin_name(x: Any) -> bool:
    return isinstance(x, type(None))


values: list[Any] = [None, 3, True, "s", 2.5, [None]]
print([tested(v) for v in values])
print([either(v) for v in values])
print([builtin_name(v) for v in values])
