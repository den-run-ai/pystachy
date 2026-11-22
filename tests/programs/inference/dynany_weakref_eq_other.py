# pystachy: dynamic-any
# A weak reference held as an Any value is unequal to a value that is no weak reference, in
# either operand order, as CPython's returns NotImplemented for it; two references compare
# their referents, of one class or of two. An ordering raises TypeError, and searches of Any
# lists pass over other values, as a dict or a set does that holds a reference beside a key of
# its hash.
import weakref
from typing import Any


class Node:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Node) and self.n == other.n

    def __hash__(self) -> int:
        return self.n


class Leaf:
    pass


def eq(a: Any, b: Any) -> str:
    return f"{a == b}{b == a}{a != b}{b != a}"


def less(a: Any, b: Any) -> str:
    try:
        return str(a < b)
    except TypeError:
        return "TypeError"


one = Node(1)
twin = Node(1)
two = Node(2)
leaf = Leaf()
ref: Any = weakref.ref(one)
others: list[Any] = [5, "a", [1], None, 2.5, (1, 2), {"k": 1}, True, one]
print(" ".join(eq(ref, o) for o in others))
print(ref in others, others.count(ref), less(ref, 5), less(5, ref))

same: Any = weakref.ref(twin)
other: Any = weakref.ref(two)
leafy: Any = weakref.ref(leaf)
print(eq(ref, ref), eq(ref, same), eq(ref, other), eq(ref, leafy), eq(leafy, leafy))
mixed: list[Any] = [5, other, leafy, same]
print(ref in mixed, mixed.index(ref), mixed.count(ref), less(ref, same))

table: dict[Any, Any] = {1: "int", ref: "ref"}
seen: set[Any] = {1, ref, "a"}
print(hash(ref) == hash(1), len(table), table[1], table[ref], len(seen), ref in seen, 1 in seen)
