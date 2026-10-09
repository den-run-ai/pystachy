# A list or dict printed again while it is being printed (a cycle through an object whose
# __repr__ prints it) shows as [...] or {...}, as CPython's reprs of lists and dicts do.
class Node:
    def __init__(self, name: str) -> None:
        self.name = name
        self.kids: list[Node] = []
        self.index: dict[str, Node] = {}

    def __repr__(self) -> str:
        return f"Node({self.name}, {self.kids}, {self.index})"


n = Node("a")
print(n)
n.kids.append(n)
n.index["self"] = n
n.kids.append(Node("b"))
print(n)
print([n], {"k": [n]}, (n.kids, 1), str(n.kids), repr(n.index))
m = Node("m")
m.index["n"] = n
n.index["m"] = m
print(m)
print(f"{n.kids!r}")
