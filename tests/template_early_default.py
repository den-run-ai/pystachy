# A call compiled before the def or class statement of the function it calls runs (in a
# template's function called first in a branch that does not run, or in a function compiled
# early for a global's type): a default value that is no constant is still evaluated once,
# when the def or class statement runs.
import sys
from dataclasses import dataclass


def t(x):
    return g(x) + h()


def make(x):
    return Item(x)


def count(x):
    return Counter(x).total()


if len(sys.argv) > 5:
    print(t(1), make(1), count(1))


def g(x, opt=len(sys.argv) * [0]):
    opt.append(x)
    return len(opt)


def h(acc: list[int] = []) -> int:
    acc.append(1)
    return len(acc)


def tag() -> str:
    print("tag evaluated")
    return "t"


def start() -> int:
    print("start evaluated")
    return 10


@dataclass
class Item:
    n: int
    label: str = tag()


class Counter:
    base: int = start()

    def __init__(self, step: int):
        self.step = step

    def total(self) -> int:
        return self.base + self.step


print(t(2), t(3))
print(make(2), make(3))
print(count(2), count(3))

NODES = []


def nodes() -> None:
    print(NODES)


class Node:
    tag: str = "n" * 2

    def __init__(self, v: int):
        self.v = v
        NODES.append(v)


nodes()
n = Node(3)
print(NODES, n.tag)
