# error: expected Holder[int], got Holder[str]
# Distinct field layouts remain distinct static object types.
from typing import Any


class Holder:
    def __init__(self, value: Any) -> None:
        self.value = value


h = Holder(1)
h = Holder("changed")
