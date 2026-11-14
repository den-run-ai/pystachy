# A class whose field is a tuple of its own objects (#637): a recursive annotation under
# postponed evaluation, an empty default, traversal, the identity of a tuple passed on as it is
# (one annotated so: a fixed tuple converts, tests/deviations/tuple_runtime_identity.py) and errors
from __future__ import annotations


class Node:
    def __init__(self, label: str, children: tuple[Node, ...] = ()) -> None:
        self.label = label
        self.children = children

    def walk(self, depth: int) -> list[str]:
        out = ["  " * depth + self.label]
        for child in self.children:
            out.extend(child.walk(depth + 1))
        return out


leaf = Node("leaf")
kids: tuple[Node, ...] = (leaf, Node("other", (Node("deep"),)))
root = Node("root", kids)
print(len(Node("x", (Node("y"),)).children), len(leaf.children))
print("\n".join(root.walk(0)))
print(root.children is kids, root.children[0] is leaf, root.children[-1].children[0].label)
try:
    print(leaf.children[0])
except IndexError as e:
    print("IndexError:", e)
