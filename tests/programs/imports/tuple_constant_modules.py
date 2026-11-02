# Equal tuple constants of two modules are two objects: CPython compiles each module apart and
# merges the constants of one. The empty tuple is one object everywhere (#1016).
from tconstmods.other import empty, label, origin


def mine() -> tuple[int, int]:
    return (0, 0)


def none() -> tuple[()]:
    return ()


def named() -> tuple[str, int]:
    return ("origin", 0)


print(origin() is origin(), mine() is mine(), origin() is mine(), origin() == mine())
print(empty() is none(), empty() is empty(), none() is none())
print(label() is label(), label() is named(), label()[0] is named()[0], label() == named())
