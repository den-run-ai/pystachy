import struct
import sys


class Node:
    def __init__(self, kind: int, start: int, end: int) -> None:
        self.kind = kind
        self.start = start
        self.end = end
        self.a: Node | None = None
        self.xs: list[Node] = []
        self.name = b""
        self.fval = 0.0


def walk(n: Node) -> int:
    total = n.kind
    a = n.a
    if a is not None:
        total += walk(a)
    for x in n.xs:
        total += walk(x)
    return total


root = Node(1, 0, 10)
child = Node(2, 1, 3)
root.a = child
root.xs.append(Node(3, 4, 5))
root.name = b"abc"
print(walk(root), root.name, len(root.name))
data = "é = 'ü'\n".encode()
print(len(data), data[0], data[1], data[2:5], data.find(b"="), data[0:2].decode())
s = "éü"
print(len(s))
d: dict[bytes, int] = {b"if": 1, b"else": 2}
print(d.get(b"if", 0), d.get(b"zz", -1))
print(struct.pack("<d", float("1e308")).hex(), struct.pack("<d", float("0.1")).hex())
print(sys.platform, sys.version_info[0], sys.version_info[1])
parts = [b"a", b"bc"]
print(b"".join(parts), b"x" + b"y", bytes([65, 66]))
print(data.startswith(b"\xc3"), b"ab" in b"xaby")
