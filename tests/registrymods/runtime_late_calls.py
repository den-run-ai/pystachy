# pystachy: dynamic-any
from typing import Any


class Late:
    def __add__(self, other: Any) -> int:
        return len(globals())


class Holder:
    def get(self) -> Any:
        return Late()
