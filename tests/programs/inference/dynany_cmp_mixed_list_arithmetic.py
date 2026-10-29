# pystachy: dynamic-any
# Differently typed field arithmetic must still execute the comparison body.
from typing import Any


class Peer:
    def __init__(self) -> None:
        self.items = ["different", "storage"]


class Strict:
    def __init__(self) -> None:
        self.items = [3, 4]

    def __eq__(self, other: "Strict") -> bool:
        print("comparison ran")
        return len(self.items + other.items) == 4

    def __lt__(self, other: "Strict") -> bool:
        print("ordering ran")
        return (self.items + other.items)[-1] == "storage"


x: Any = Strict()
y: Any = Peer()
print(x == y, y == x)
print(x < y, y > x)
print(y in [x])
