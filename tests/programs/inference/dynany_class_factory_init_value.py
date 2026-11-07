# pystachy: dynamic-any
# A new adapter must not activate an unusable default through a saved __init__.
from typing import Any


class Current:
    def __init__(self, value: int = 0) -> None:
        self.value = value


class Dormant:
    def __init__(self, value: int = "unused") -> None:
        self.value = value


seed: Any = Current(1)
unused: Any = Dormant
function: Any = seed.__init__
function()
print(seed.value)
