# The reprs of deep object trees are limited by the native stack, not by the recursive-alias
# budget (512 alias edges): a dataclass's generated __repr__ and a class's own __repr__ both
# print deeper trees, as CPython does.
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Node:
    name: str
    children: list[Node]


class Plain:
    def __init__(self, kids: list[Plain]) -> None:
        self.kids = kids

    def __repr__(self) -> str:
        return "P" + repr(self.kids)


def main() -> None:
    n = Node("leaf", [])
    for i in range(300):
        n = Node("n", [n])
    text = repr(n)
    print(len(text), text[:40], text[-20:])
    p = Plain([])
    for i in range(700):
        p = Plain([p])
    text = repr(p)
    print(len(text), text[:12], text[-12:])
    print(len(str([n, n])), len(repr({"p": p})))


main()
