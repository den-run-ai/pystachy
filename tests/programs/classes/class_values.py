# A class of the program is a value (#7): its class object, typed type[C], is kept in variables,
# parameters, fields, containers and defaults. Each class has one, so identity compares and hashes
# class objects; str() and repr() give CPython's text, and __name__, __qualname__ and __module__
# its names. type[A] holds the class object of A or of a class deriving from A
class Node:
    pass


class Leaf(Node):
    pass


class Branch(Node):
    def __init__(self) -> None:
        self.kids: list[Node] = []


class Registry:
    def __init__(self, kind: type[Node], fallback: type[Node] = Leaf) -> None:
        self.kind = kind
        self.fallback = fallback

    def names(self) -> tuple[str, str]:
        return (self.kind.__name__, self.fallback.__name__)


DEFAULT: type[Node] = Branch


def same(a: type[Node], b: type[Node]) -> tuple[bool, bool, bool, bool]:
    return (a is b, a is not b, a == b, a != b)


def choose(flag: bool) -> type[Node]:
    return Leaf if flag else DEFAULT


def default_kind(kind: type[Node] = Node) -> str:
    return kind.__name__


def versus(c: type[Node] | None, s: str | None, o: Node | None) -> tuple[bool, bool, bool, bool, bool]:
    # (a class object is no value of another type, but None is None)
    return (c == s, c != s, c == o, c is o, o is not c)


def truth(k: type[Node] | None) -> str:
    out = "set" if k else "unset"
    if not k:
        out += " not"
    fallback = k or Node
    return out + " " + fallback.__name__ + " " + str(bool(k))


print(Node, [Node, Leaf], (Leaf, Branch), {"a": Leaf})
print(same(Leaf, Leaf), same(Leaf, Branch), same(Node, Leaf))
k: type[Node] = Leaf
print(k is Leaf, k is Node, k == Leaf, k != Branch, Leaf is k)
print(k.__name__, k.__qualname__, k.__module__, Leaf.__qualname__, Leaf.__module__)
print(k, str(k), repr(k), f"{k}", f"{k!r}", "%s" % k)
print(callable(k), isinstance(k, type), type(k).__name__)
print(k == 1, k != "Leaf", k == KeyError, k is None, k is not None, 1 == k)
leaf = Leaf()
print(k == leaf, leaf != k, leaf is k)
print(versus(None, None, None), versus(Leaf, None, None), versus(None, "x", Leaf()), versus(Leaf, "Leaf", Leaf()))
r = Registry(Branch)
print(r.names(), Registry(Node, Branch).names(), r.kind is Branch, r.fallback)
print(choose(True).__name__, choose(False).__name__, default_kind(), default_kind(Leaf))
DEFAULT = Node
print(choose(False).__name__, DEFAULT is Node)
print(truth(None), "|", truth(Leaf), "|", truth(Node))
# in containers: lists, tuples, dict values and keys, sets
kinds: list[type[Node]] = [Branch, Leaf, Node, Leaf]
print(kinds.index(Leaf), kinds.count(Leaf), Branch in kinds, kinds == [Branch, Leaf, Node, Leaf], kinds[1:] == [Leaf, Node], kinds != [Branch])
print(sorted([c.__name__ for c in kinds]), [c.__name__ for c in sorted(kinds, key=lambda c: c.__name__)])
kinds.append(Branch)
kinds.remove(Node)
print([c.__name__ for c in kinds], [c.__name__ for c in reversed(kinds)], len(set(kinds)))
nodes: list[Node] = [Leaf(), Branch(), Leaf(), Node(), Branch(), Leaf()]
seen: dict[type[Node], int] = {}
for n in nodes:
    seen[type(n)] = seen.get(type(n), 0) + 1
print(seen[Leaf], seen[Branch], seen[Node], len(seen), Leaf in seen, seen)
print([(c.__name__, seen[c]) for c in seen], seen.get(Branch), seen.pop(Node), Node in seen)
group: set[type[Node]] = {Leaf, Branch, Leaf}
print(len(group), Leaf in group, Node in group, sorted([c.__name__ for c in group]))
print(hash(Leaf) == hash(k), hash(Leaf) == hash(Branch))
pair: tuple[type[Node], str] = (Branch, "ok")
print(pair[0].__name__, pair, pair == (Branch, "ok"), pair[0] in (Leaf, Branch))
siblings = [Leaf, Branch]
handlers = {Leaf: "leaf", Branch: "branch"}
labels = {"l": Leaf, "b": Branch}
both = {Branch, Leaf}
print([c.__name__ for c in siblings], handlers[Branch], handlers[type(nodes[0])], labels["b"].__name__, len(both), Node in both)
a: type[Node] = Leaf
b: type[Node] = Branch
a, b = b, a
print(a.__name__, b.__name__, (a, b) == (Branch, Leaf))
maybe: type[Node] | None = None
print(maybe is None, maybe == Leaf, maybe)
maybe = Branch
print(maybe is None, maybe == Branch, maybe, maybe.__name__ if maybe is not None else "-")
try:
    print(sorted([Leaf, Branch]))
except TypeError as e:
    print("TypeError:", e)
