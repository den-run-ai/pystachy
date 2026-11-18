# pystachy: dynamic-any
from typing import Any
from mods.constructor_dependency import NestedErrors, Options


class Dormant:
    def __init__(self, value: int) -> None:
        self.value: int = NestedErrors(Options(value > 0)).count()


class Active:
    def __init__(self, value: int) -> None:
        self.value: int = value


# Trying the unused constructor adapter must not retain its layout discoveries.
factory: Any = Dormant
active: Any = Active
print(active(4).value)
