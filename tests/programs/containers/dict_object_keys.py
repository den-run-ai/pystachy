# objects of classes that define neither __eq__ nor __hash__ as dict keys: hashed and compared by
# identity, as object's __hash__ and __eq__ do; lookups, insertion order, deletion, printing (a
# KeyError names the key by its __repr__), copies, equality, tuple keys and None as a key


class Node:
    def __init__(self, name: str) -> None:
        self.name = name
        self.edges: list[Node] = []

    def __repr__(self) -> str:
        return f"Node({self.name!r})"


class Leaf(Node):
    pass


class Plain:
    pass


a = Node("a")
b = Node("b")
c = Leaf("ç")
a.edges = [b, c]
b.edges = [a, c]
c.edges = [a]

depth: dict[Node, int] = {a: 0}
depth[b] = 1
depth[c] = 2
print(depth, len(depth))
print(depth[c], b in depth, Node("a") in depth, Node("a") not in depth)
depth[a] = 5  # (a key it holds: the value changes, the order does not)
print(depth)
del depth[b]
print(depth, depth.get(b), depth.get(b, -1), depth.pop(c), depth.setdefault(b, 7), depth)
print(list(depth.keys()), list(depth.values()), list(depth.items()))
try:
    print(depth[Node("x")])
except KeyError as e:
    print("KeyError", e, repr(e))
try:
    depth.pop(c)
except KeyError as e:
    print("KeyError", e)
try:
    del depth[c]
except KeyError as e:
    print("KeyError", e)
print(depth.pop(c, 9), depth.get(c) is None)


def bfs(start: Node) -> list[str]:
    # a visited dict keyed by the nodes themselves
    dist: dict[Node, int] = {start: 0}
    order = [start]
    i = 0
    while i < len(order):
        n = order[i]
        i += 1
        for m in n.edges:
            if m not in dist:
                dist[m] = dist[n] + 1
                order.append(m)
    return [f"{n.name}:{dist[n]}" for n in order]


print(bfs(a), bfs(c))

counts: dict[Node, int] = {}
for n in [a, b, a, c, a, b]:
    counts[n] = counts.get(n, 0) + 1
for n in [c, c]:
    counts[n] += 10
print(counts)
groups: dict[Node, list[str]] = {}
for n, w in [(a, "x"), (b, "y"), (a, "z")]:
    groups.setdefault(n, []).append(w)
print(groups)

# copies, equality, fromkeys, update, iteration
d2 = dict(counts)
d3 = counts.copy()
print(d2 == counts, d3 == counts, d2 is counts, d2 == {a: 3, b: 2, c: 11}, d2 == {a: 3, b: 2, c: 1})
d3[Leaf("new")] = 0
print(d3 != counts, len(d3))
d4 = dict.fromkeys([b, c, a, c], 0)
print(d4)
d4.update(counts)
print(d4)
d5 = dict.fromkeys(counts, "v")
print(d5)
print([n.name for n in counts], [n.name for n in reversed(list(counts))])
for n, v in counts.items():
    print(n.name, v, end="; ")
print()
order: list[str] = []
for n in counts:
    order.append(n.name)
print(order, sorted(counts, key=lambda n: n.name))

# tuple keys with objects, and None as a key (a Node | None)
pairs: dict[tuple[Node, int], str] = {(a, 1): "x", (b, 2): "y"}
print(pairs[(a, 1)], (a, 2) in pairs, (b, 2) in pairs, (Node("a"), 1) in pairs)
pairs[(a, 1)] = "z"
pairs[(c, 1)] = "w"
del pairs[(b, 2)]
print(pairs)
nested: dict[tuple[str, tuple[Node, bool]], int] = {("k", (a, True)): 1}
print(nested[("k", (a, True))], ("k", (a, False)) in nested)
maybe: dict[Node | None, str] = {None: "none", a: "a"}
print(maybe, None in maybe, maybe[None], maybe.get(b, "?"))
del maybe[None]
print(maybe, None in maybe)
p1 = Plain()
p2 = Plain()
plain = {p1: 1, p2: 2}
print(plain[p1], plain[p2], len(plain), Plain() in plain)


class Graph:
    # keys inside methods and fields
    def __init__(self) -> None:
        self.ids: dict[Node, int] = {}

    def add(self, n: Node) -> int:
        if n not in self.ids:
            self.ids[n] = len(self.ids)
        return self.ids[n]


g = Graph()
print([g.add(n) for n in [b, a, b, c, a]], g.ids)


def make_counter() -> dict[Node, int]:
    seen: dict[Node, int] = {}

    def visit(n: Node) -> int:
        seen[n] = seen.get(n, 0) + 1
        return seen[n]

    print([visit(a), visit(b), visit(a), visit(a)])
    return seen


print(make_counter())
many: dict[Node, int] = {}
nodes = [Node(str(i)) for i in range(2000)]
for i in range(len(nodes)):
    many[nodes[i]] = i
for i in range(0, len(nodes), 2):
    del many[nodes[i]]
print(len(many), sum(many.values()), many[nodes[1999]], nodes[0] in many, nodes[1] in many)


class Vec:
    # (a key class whose name holds a V, a value class whose name holds a K: dict methods' types)
    def __init__(self, n: int) -> None:
        self.n = n

    def __repr__(self) -> str:
        return f"Vec{self.n}"


class Kit:
    def __init__(self, s: str) -> None:
        self.s = s

    def __repr__(self) -> str:
        return f"Kit({self.s})"


v1 = Vec(1)
v2 = Vec(2)
kits: dict[Vec, Kit] = {v1: Kit("a")}
kits.setdefault(v2, Kit("b"))
print(kits.get(v1), kits.get(Vec(1)), list(kits.items()), list(kits.keys()), list(kits.values()), kits.pop(v2), kits)
pairs2: dict[tuple[Vec, Kit], list[Kit]] = {}
k1 = Kit("k")
pairs2.setdefault((v1, k1), []).append(Kit("x"))
print(pairs2.get((v1, k1)), list(pairs2.items()))
