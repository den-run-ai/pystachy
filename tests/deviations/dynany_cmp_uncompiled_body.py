# pystachy: dynamic-any
# Remaining #803 gap: a comparison body that reads its operand back out of a container does not
# compile for an operand of another class, so the call falls back to identity and skips the body,
# where CPython prints "comparison ran" and True.
from typing import Any


class Holder:
    def __init__(self) -> None:
        self.items = [1]

    def __eq__(self, other: "Holder") -> bool:
        print("comparison ran")
        box = [other]
        return len(box[0].items) == len(self.items)


class Peer:
    def __init__(self) -> None:
        self.items = ["x"]


a: Any = Holder()
b: Any = Peer()
print(a == b)
