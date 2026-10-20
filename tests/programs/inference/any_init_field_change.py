# A field typed by an Any parameter's argument, given a value of another type: their union.
from typing import Any


class Holder:
    def __init__(self, value: Any) -> None:
        self.value = value


h = Holder(1)
print(h.value)
h.value = "changed"
print(repr(h.value))
