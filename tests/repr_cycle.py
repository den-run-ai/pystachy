from dataclasses import dataclass
from typing import Optional


@dataclass
class Node:
    name: str
    parent: Optional["Node"]
    children: list["Node"]


root = Node("root", None, [])
kid = Node("kid", root, [])
root.children.append(kid)
print(kid)
print(root)
