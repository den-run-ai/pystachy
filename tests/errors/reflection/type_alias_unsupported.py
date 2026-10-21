# error: type_alias_unsupported.py:9: error: Callable[..., R] is not supported: name the parameter types (Callable[[A, B], R])
# An alias's value is checked where an annotation names it (here, as the def's annotation);
# a string value, a forward reference, is evaluated there too.
from typing import Callable, TypeAlias

Fn: TypeAlias = "Callable[..., int]"


def call(g: Fn) -> int:
    return g()


print(call(lambda: 1))
