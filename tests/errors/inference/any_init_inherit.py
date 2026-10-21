# error: inheritance with generic class templates is not supported: annotate __init__ parameters with concrete types (not Any or object)
from typing import Any


class Holder:
    def __init__(self, value: Any) -> None:
        self.value = value


class Derived(Holder):
    pass


print(Derived(1).value)
