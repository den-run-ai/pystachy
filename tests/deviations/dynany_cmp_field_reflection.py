# pystachy: dynamic-any
# Late comparison fields retain native storage; general __dict__ order is #486.
from typing import Any


class Peer:
    pass


class Writer:
    def __init__(self) -> None:
        self.items = [3]

    def __eq__(self, other: "Writer") -> bool:
        other.items = self.items
        return True


original = Peer()
writer: Any = Writer()
peer: Any = original
print(vars(original))
print(writer == peer)
try:
    print(vars(original))
except TypeError as error:
    print(error)
