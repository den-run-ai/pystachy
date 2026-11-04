# pystachy: dynamic-any
# Deep-copy memo entries are shared by native and Any views in either traversal order.
import copy
from typing import Any


def same(left: Any, right: Any) -> bool:
    return left is right


class NativeFirst:
    def __init__(self, values: list[int]):
        self.native = values
        self.dynamic: Any = values


class AnyFirst:
    def __init__(self, values: list[int]):
        self.dynamic: Any = values
        self.native = values


def check(original):
    cloned = copy.deepcopy(original)
    print(cloned.native is cloned.dynamic, cloned.native is not original.native)
    print(same(cloned.native[0], original.native[0]))
    cloned.dynamic.append(7)
    cloned.native.append(8)
    print(cloned.native, cloned.dynamic, original.native)


item = int("1000")
values: list[int] = [item]
check(NativeFirst(values))
check(AnyFirst(values))
graph: list[Any] = []
graph.extend([values, values, graph])
cloned = copy.deepcopy(graph)
print(cloned[0] is cloned[1], cloned[0] is not values, cloned[2] is cloned)
print(cloned[0][0] is item)
cloned[0].append(9)
print(cloned[1], values)
# A shallow dynamic copy remains an unrestricted fresh boxed list.
dynamic: Any = values
shallow = copy.copy(dynamic)
shallow.append("free")
print(shallow, values, shallow[0] is item)
