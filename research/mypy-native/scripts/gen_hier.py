"""Generate a visitor-style program: N node subclasses, each overriding accept(); M base-typed call sites."""
import sys
n, m = int(sys.argv[1]), int(sys.argv[2])
out = ["class Visitor:"]
for i in range(n):
    out.append(f"    def visit_n{i}(self, o: 'N{i}') -> int:\n        return o.v + {i}")
out.append("class Node:\n    def accept(self, v: Visitor) -> int:\n        return -1")
for i in range(n):
    out.append(f"class N{i}(Node):\n    def __init__(self, v: int) -> None:\n        self.v = v\n    def accept(self, v: Visitor) -> int:\n        return v.visit_n{i}(self)")
for j in range(m):
    out.append(f"def site{j}(x: Node, v: Visitor) -> int:\n    return x.accept(v) + {j}")
out.append("nodes: list[Node] = [" + ", ".join(f"N{i}({i})" for i in range(n)) + "]")
out.append("vis = Visitor()\ntotal = 0")
out.append("for x in nodes:")
for j in range(m):
    out.append(f"    total += site{j}(x, vis)")
out.append("print(total)")
print("\n".join(out))
