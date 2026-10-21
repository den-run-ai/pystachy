# objects of classes that define neither __eq__ nor __hash__ as set and frozenset elements: by
# identity; visited sets, membership, removal, the set operators and methods, comprehensions.
# The order of such a set depends on the objects' addresses (in CPython too): sorted() orders
# what is printed


class Node:
    def __init__(self, name: str, edges: list["Node"]) -> None:
        self.name = name
        self.edges = edges

    def __repr__(self) -> str:
        return f"<{self.name}>"


def names(s) -> list[str]:  # (a set or a frozenset of Node)
    return sorted([n.name for n in s])


def reachable(start: Node) -> set[Node]:
    seen: set[Node] = set()
    todo = [start]
    while todo:
        n = todo.pop()
        if n in seen:
            continue
        seen.add(n)
        for m in n.edges:
            if m not in seen:
                todo.append(m)
    return seen


d = Node("d", [])
c = Node("c", [d])
b = Node("b", [c, d])
a = Node("a", [b, c])
d.edges.append(a)
e = Node("é", [])
print(names(reachable(a)), names(reachable(e)), len(reachable(c)))

s = {a, b, c}
print(len(s), a in s, d in s, Node("a", []) in s, e not in s, {a}, {e} == {e}, {a} == {Node("a", [])})
s.add(a)
s.add(d)
print(len(s), names(s))
s.discard(a)
s.discard(a)
s.discard(e)
print(names(s))
try:
    s.remove(a)
except KeyError as x:
    print("KeyError", x)
s.remove(b)
print(names(s), s.pop() in {c, d}, len(s))
s.clear()
print(s, len(s))

x = {a, b, c}
y = {b, c, d}
print(names(x | y), names(x & y), names(x - y), names(x ^ y))
print(x <= y, x & y <= x, (x & y) < x, x >= (x - y), x.isdisjoint({d, e}), x.isdisjoint(y))
print(x.issubset([a, b, c, d]), x.issuperset([a, b]), x.issuperset([a, e]))
print(names(x.union([d], (e,))), names(x.intersection([b, d])), names(x.difference([a], [b])))
print(names(x.symmetric_difference([c, d])))
z = set(x)
z |= {e}
z &= {a, e, d}
print(names(z))
z -= {a}
z ^= {b, e}
print(names(z))
z.update([c], {d})
z.difference_update([b])
z.intersection_update([c, d, e])
z.symmetric_difference_update([d])
print(names(z))
f = frozenset([a, b])
g = frozenset({b, c})
print(len(f), a in f, names(f | g), names(f & g), names(f - g), f == frozenset([b, a]), f != g)
empty: frozenset[Node] = frozenset()
print(frozenset([a]), empty == s, names(frozenset(x) - f))
print(names({n for n in [a, b, c, a] if n is not b}), len({n.name for n in [a, b, a]}))
print(names(set({a: 1, b: 2})), names(set([d, d, c])), sorted([n.name for n in list({c})]))

pairs = {(a, 1), (b, 2), (a, 1)}
print(len(pairs), (a, 1) in pairs, (a, 2) in pairs, (Node("a", []), 1) in pairs)
many = set([Node(str(i), []) for i in range(3000)])
first = [n for n in many if n.name == "7"][0]
print(len(many), first in many, Node("7", []) in many)
many.discard(first)
print(len(many), first in many)
