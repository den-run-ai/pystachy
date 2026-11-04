# pystachy: dynamic-any
# pystachy: python-int
# A dynamic deep copy retains wide items and their identity after the native owner leaves.
import copy
from typing import Any


def same(left: Any, right: Any) -> bool:
    return left is right


class Pair:
    def __init__(self, values: list[int]):
        self.dynamic: Any = values
        self.native = values


def make() -> Pair:
    values: list[int] = [int("18446744073709551623")]
    return Pair(values)


original = make()
cloned = copy.deepcopy(original)
print(cloned.dynamic is cloned.native, cloned.native is not original.native)
print(cloned.native[0], same(cloned.native[0], original.native[0]))
cloned.dynamic.append(2**90)
cloned.native.append(2**100)
print(cloned.dynamic, original.dynamic)
print(sum(cloned.native), sum(cloned.dynamic))
