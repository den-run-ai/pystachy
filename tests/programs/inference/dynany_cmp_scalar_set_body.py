# pystachy: dynamic-any
# The original #803 set-field comparison must execute its method body.
from typing import Any


class Peer:
    def __init__(self) -> None:
        self.items: set[str] = {"different storage"}


class Strict:
    def __init__(self) -> None:
        self.items: set[int] = {3}

    def __eq__(self, other: "Strict") -> bool:
        print("comparison ran")
        return self.items == other.items


x: Any = Strict()
y: Any = Peer()
print(x == y)
