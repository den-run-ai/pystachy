# pystachy: dynamic-any
# A failed optional initializer must not retain a global storage-widening hint.
from typing import Any
from registrymods.factory_only import ColdHints, stable


def identity(value: int) -> int:
    return value


registry: dict[Any, Any] = {ColdHints: identity}
print(registry[ColdHints](4), identity(stable))
