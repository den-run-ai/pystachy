# pystachy: dynamic-any
# Class values support registry keys; calls through them remain a prototype gap.
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
