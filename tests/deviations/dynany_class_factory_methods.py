# pystachy: dynamic-any
# Factory-only preparation does not introduce user method/protocol dispatch.
from typing import Any


class Record:
    def __init__(self, value: int) -> None:
        self.value = value

    def read(self) -> int:
        return self.value


factory: Any = Record
try:
    print(factory(7).value)
except NotImplementedError as exc:
    print(str(exc))
