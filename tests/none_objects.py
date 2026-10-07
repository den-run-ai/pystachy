# None-valued objects, dataclass __repr__/__eq__ on recursive types, __bool__/__len__ truthiness
from dataclasses import dataclass
from typing import Optional


@dataclass
class Node:
    val: int
    nxt: Optional["Node"] = None


class V:
    def __init__(self, x: int):
        self.x = x

    def __add__(self, o: "V") -> "V":
        return V(self.x + o.x)

    def __eq__(self, o: "V") -> bool:
        return o is not None and self.x == o.x

    def __repr__(self) -> str:
        return f"V({self.x})"

    def __str__(self) -> str:
        return f"<{self.x}>"


class Sized:
    def __init__(self, n: int):
        self.n = n

    def __len__(self) -> int:
        return self.n


class Flag:
    def __init__(self, b: bool):
        self.b = b

    def __bool__(self) -> bool:
        return self.b


def find(n: Optional[Node], v: int) -> Optional[Node]:
    while n is not None:
        if n.val == v:
            return n
        n = n.nxt
    return None


lst = Node(1, Node(2, Node(3)))
print(lst, find(lst, 2), find(lst, 9))
print(lst == Node(1, Node(2, Node(3))), lst == Node(1, Node(2)), lst != lst.nxt, lst == None, None == lst)
none_node: Optional[Node] = find(lst, 7)
print(none_node == None, none_node == lst, str(none_node), repr(none_node), f"{none_node}|{none_node!r}")
v = V(1)
w: Optional[V] = None
print(v, repr(v), str(v), f"{v!r} {v}", v + V(2), v == V(1), v == w, w == v, w == w, w != v)
print(bool(Sized(0)), bool(Sized(2)), "yes" if Flag(True) else "no", "yes" if Flag(False) else "no", not Sized(3), len(Sized(4)))
s: Optional[Sized] = None
print(bool(s), "t" if s else "f")
print(find(lst, 3).val)
