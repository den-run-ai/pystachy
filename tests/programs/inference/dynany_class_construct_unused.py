# pystachy: dynamic-any
# An unused class key/value cannot force its unsupported initializer to compile.
from typing import Any
from registrymods.construct_unused import Unused


def identity(value: int) -> int:
    return value


registry: dict[Any, Any] = {Unused: identity, "unused": Unused}
print(registry[Unused](7))
print(registry["unused"] is Unused, type(registry["unused"]) is type)
