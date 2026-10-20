# Item assignment and deletion dispatch through the existing method specializations, preserving
# evaluation order and explicit parameter contexts. Any does not make the fields dynamic.
from typing import Any

from mods.any_mutation import Table


def mark(key: str) -> str:
    print("key", key)
    return key


def value(n: int) -> int:
    print("value", n)
    return n


class Stack:
    def __init__(self) -> None:
        self.items: list[list[int]] = [[1]]

    def __setitem__(self, key: Any, value: list[int]) -> None:
        self.items[int(key)] = value


class Plain:
    def __init__(self) -> None:
        self.items = [1, 2]

    def __setitem__(self, key, value):
        self.items[int(key)] = int(value)

    def __delitem__(self, key):
        del self.items[int(key)]


class Derived(Table):
    pass


def touch(t: Table) -> None:
    t[2] = "5"
    print(t[2])
    del t[2]


t = Table()
t[1] = "12"
t[mark("x")] = value(3)
t[mark("x")] += value(4)
print(t.items)
del t[1]
del t[mark("x")]
print(t.items)
s = Stack()
s["0"] = []
print(s.items)
p = Plain()
p["0"] = "3"
del p[1]
print(p.items)
touch(Derived())
