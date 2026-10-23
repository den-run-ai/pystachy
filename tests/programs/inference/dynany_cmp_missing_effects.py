# pystachy: dynamic-any
from typing import Any


def announce(label: str) -> list[int]:
    print(label)
    return [3]


class Peer:
    def __init__(self) -> None:
        self.count = 0


class Strict:
    def __init__(self, mode: int) -> None:
        self.items = [3]
        self.count = 0
        self.mode = mode

    def __eq__(self, other: "Strict") -> bool:
        print("entered", self.mode)
        other.count += 1
        if self.mode == 0:
            return True or self.items == other.items
        if self.mode == 1:
            return False and self.items == other.items
        if self.mode == 2:
            raise ValueError("first error")
        if self.mode == 3:
            return True if self.mode == 3 else self.items == other.items
        if self.mode == 4:
            return announce("before read") == other.items
        return other.items == announce("must not run")


peer = Peer()
y: Any = peer
for mode in range(6):
    x: Any = Strict(mode)
    try:
        print(x == y)
    except ValueError as exc:
        print(str(exc))
    except AttributeError as exc:
        print(str(exc))
    print("count", peer.count)

# Reflected equality, inherited bodies, inversion for != and container search
# must retain the same first error and the write to an existing field.
class Inherited(Strict):
    pass


x = Inherited(4)
try:
    print(y == x)
except AttributeError as exc:
    print(str(exc))
try:
    print(x != y)
except AttributeError as exc:
    print(str(exc))
try:
    print(y in [x])
except AttributeError as exc:
    print(str(exc))
print("count", peer.count)

# The ordinary same-class specialization remains available.
print(Strict(4) == Strict(4))
