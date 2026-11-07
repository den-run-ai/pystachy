# pystachy: dynamic-any
# Stored ordinary classes construct their existing fixed native layouts.
from typing import Any


class Empty:
    pass


class Box:
    def __init__(self, value: int) -> None:
        self.value = value


class Pair:
    def __init__(self, left: int, right: str) -> None:
        self.left = left
        self.right = right


# Reconstruct the ordinary layouts already present in a heterogeneous program.
originals: list[Any] = [Empty(), Box(0), Pair(0, "source")]
empty: Any = type(originals[0])
first = empty()
second = empty()
print(type(first) is Empty, type(second) is Empty, first is second)

box: Any = type(originals[1])
one = box(7)
print(type(one) is Box, one.value)
pair: Any = Pair
two = pair(11, "pair")
print(type(two) is Pair, two.left, two.right)

# The class returned from type() must reach the same constructor as its name.
saved: Any = type(two)
again = saved(13, "again")
print(saved is Pair, type(again) is Pair, again is two)
print(again.left, again.right, two.left, two.right)
