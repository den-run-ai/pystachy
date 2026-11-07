# pystachy: dynamic-any
# A concrete annotation-backed class can be constructed without an exemplar.
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
