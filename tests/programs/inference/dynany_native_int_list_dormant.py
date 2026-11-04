# pystachy: dynamic-any
# Native list[int] becoming boxable must not let an unrelated variadic tuple
# field fail later, outside the comparison's concrete-specialization retry.
from typing import Any


class Strict:
    def __init__(self):
        self.force = [1]
        self.items = (1, 2)

    def __eq__(self, other):
        return self.force == other.force and self.items == other.items


class Peer:
    def __init__(self):
        self.force = [1]
        self.items = (1, 2)


x: Any = Strict()
y: Any = Peer()
print("matching", x == y)


class VariablePeer:
    def __init__(self):
        self.force = [1]
        self.items: tuple[str, ...] = ("1", "2")


# This class must not poison the earlier comparison merely by being boxed.
# Its own comparisons still use the existing concrete tuple-layout adapter.
variable: Any = VariablePeer()
print("variable", x == variable)
print("reflected", variable == x)
