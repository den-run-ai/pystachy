# pystachy: dynamic-any
# A class used only as a value has no existing boxed instance adapter to reuse.
from typing import Any


class Record:
    def __init__(self, value: int):
        self.value = value


factory: Any = Record
print(callable(factory))
try:
    print(factory(7).value)
except NotImplementedError as exc:
    print(str(exc))
