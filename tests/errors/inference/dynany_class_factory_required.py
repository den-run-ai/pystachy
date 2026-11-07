# error: unsupported call eval(str)
# pystachy: dynamic-any
# Independently required lazy bodies must not be hidden by a declined factory.
from typing import Any
from registrymods.factory_only import ColdHelper, unsupported


class Ready:
    def __init__(self, value: int) -> None:
        self.value = value


factory: Any = Ready
unused: Any = ColdHelper
print(factory(7).value)
print(unsupported(9))
