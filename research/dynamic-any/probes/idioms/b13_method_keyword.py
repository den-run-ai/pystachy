# pystachy: dynamic-any
# a method of an Any value called with a keyword argument
from typing import Any


class Fmt:
    def show(self, x: Any, width: int = 4) -> str:
        return str(x).rjust(width)


f: Any = Fmt()
print(f.show(3, width=6))
