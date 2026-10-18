# error: expected int, got str
# Inferred constructor parameters do not introduce dynamic fields.
from typing import Any


class Holder:
    def __init__(self, value: Any) -> None:
        self.value = value


h = Holder(1)
h.value = "changed"
