# pystachy: dynamic-any
"""A deepcopy-style copy of a heterogeneous object graph: the dynamic-Any acceptance workload.

One memo holds every value the traversal reaches (lists, dicts, tuples, scalars and objects of
six unrelated classes), keyed by identity. The graph has repeated references, cycles, fields
whose types change, and a copier chosen at run time by each object's type.
"""
from typing import Any, Callable


class Node:
    def __init__(self, label: str, payload: Any) -> None:
        self.label = label
        self.payload = payload
        self.children: list[Any] = []
        self.parent: Any = None


class Leaf:
    def __init__(self, value: Any) -> None:
        self.value = value


class Pair:
    def __init__(self, left: Any, right: Any) -> None:
        self.left = left
        self.right = right


class Counter:
    def __init__(self) -> None:
        self.count: Any = 0

    def bump(self) -> None:
        # int, then float, then str: the field's type changes as it runs
        if isinstance(self.count, int) and self.count >= 2:
            self.count = self.count + 0.5
        elif isinstance(self.count, float):
            self.count = "many"
        elif isinstance(self.count, int):
            self.count = self.count + 1


class Registry:
    def __init__(self) -> None:
        self.entries: dict[Any, Any] = {}

    def add(self, key: Any, value: Any) -> None:
        self.entries[key] = value


class Event:
    def __init__(self, kind: str, data: Any) -> None:
        self.kind = kind
        self.data = data


def copy_value(x: Any, memo: dict[int, Any]) -> Any:
    if x is None or isinstance(x, bool) or isinstance(x, int) or isinstance(x, float) or isinstance(x, str):
        return x  # (immutable scalars: themselves, as copy.deepcopy's atomic types)
    k = id(x)
    if k in memo:
        return memo[k]
    if isinstance(x, list):
        y: list[Any] = []
        memo[k] = y
        for item in x:
            y.append(copy_value(item, memo))
        return y
    if isinstance(x, dict):
        d: dict[Any, Any] = {}
        memo[k] = d
        for key in x:
            d[copy_value(key, memo)] = copy_value(x[key], memo)
        return d
    if isinstance(x, tuple):
        items: list[Any] = []
        for item in x:
            items.append(copy_value(item, memo))
        t = tuple(items)
        memo[k] = t
        return t
    copier = COPIERS.get(type(x).__name__)
    if copier is None:
        raise TypeError("cannot copy a " + type(x).__name__)
    return copier(x, memo)


def copy_node(x: Any, memo: dict[int, Any]) -> Any:
    n = Node(x.label, None)
    memo[id(x)] = n
    n.payload = copy_value(x.payload, memo)
    n.children = copy_value(x.children, memo)
    n.parent = copy_value(x.parent, memo)
    return n


def copy_leaf(x: Any, memo: dict[int, Any]) -> Any:
    n = Leaf(None)
    memo[id(x)] = n
    n.value = copy_value(x.value, memo)
    return n


def copy_pair(x: Any, memo: dict[int, Any]) -> Any:
    n = Pair(None, None)
    memo[id(x)] = n
    n.left = copy_value(x.left, memo)
    n.right = copy_value(x.right, memo)
    return n


def copy_counter(x: Any, memo: dict[int, Any]) -> Any:
    n = Counter()
    memo[id(x)] = n
    n.count = x.count
    return n


def copy_registry(x: Any, memo: dict[int, Any]) -> Any:
    n = Registry()
    memo[id(x)] = n
    n.entries = copy_value(x.entries, memo)
    return n


def copy_event(x: Any, memo: dict[int, Any]) -> Any:
    n = Event(x.kind, None)
    memo[id(x)] = n
    n.data = copy_value(x.data, memo)
    return n


COPIERS: dict[str, Callable[[Any, dict[int, Any]], Any]] = {
    "Node": copy_node, "Leaf": copy_leaf, "Pair": copy_pair,
    "Counter": copy_counter, "Registry": copy_registry, "Event": copy_event,
}


def render(x: Any, seen: dict[int, int], out: list[str]) -> None:
    # a canonical text of the graph: each container and object is numbered where it is first
    # reached, and named by its number where it is reached again (repeated references, cycles)
    if x is None or isinstance(x, bool) or isinstance(x, int) or isinstance(x, float) or isinstance(x, str):
        out.append(repr(x))
        return
    k = id(x)
    if k in seen:
        out.append("#" + str(seen[k]))
        return
    seen[k] = len(seen)
    out.append("@" + str(seen[k]) + ":")
    if isinstance(x, list):
        out.append("[")
        for item in x:
            render(item, seen, out)
            out.append(",")
        out.append("]")
    elif isinstance(x, dict):
        out.append("{")
        for key in x:
            render(key, seen, out)
            out.append(":")
            render(x[key], seen, out)
            out.append(",")
        out.append("}")
    elif isinstance(x, tuple):
        out.append("(")
        for item in x:
            render(item, seen, out)
            out.append(",")
        out.append(")")
    elif isinstance(x, Node):
        out.append("Node(" + x.label + " ")
        render(x.payload, seen, out)
        out.append(" ")
        render(x.children, seen, out)
        out.append(" ^")
        render(x.parent, seen, out)
        out.append(")")
    elif isinstance(x, Leaf):
        out.append("Leaf(")
        render(x.value, seen, out)
        out.append(")")
    elif isinstance(x, Pair):
        out.append("Pair(")
        render(x.left, seen, out)
        out.append(" ")
        render(x.right, seen, out)
        out.append(")")
    elif isinstance(x, Counter):
        out.append("Counter(" + repr(x.count) + ")")
    elif isinstance(x, Registry):
        out.append("Registry(")
        render(x.entries, seen, out)
        out.append(")")
    elif isinstance(x, Event):
        out.append("Event(" + x.kind + " ")
        render(x.data, seen, out)
        out.append(")")


def text(x: Any) -> str:
    out: list[str] = []
    render(x, {}, out)
    return "".join(out)


def build(seed: int) -> Any:
    root = Node("root", seed)
    shared: list[Any] = [seed, "shared", seed * 0.5]
    counter = Counter()
    for i in range(seed % 4 + 1):
        counter.bump()
    reg = Registry()
    for i in range(3):
        child = Node("c" + str(i), shared if i % 2 == 0 else (i, str(i), None))
        child.parent = root
        child.children.append(Leaf(i * seed))
        child.children.append(Pair(child, counter))
        root.children.append(child)
        reg.add(("child", i), child)
        reg.add(i * 1.5, Event("made", [child.label, i, True]))
    root.children.append(Pair(shared, shared))
    root.children.append(reg)
    reg.add("self", reg)
    reg.add(None, Leaf({"deep": [reg, root, {"k": (1, 2.0, "x")}]}))
    root.payload = {"seed": seed, "counter": counter, "flags": [True, False, None]}
    return root


def checksum(x: Any, seen: dict[int, bool]) -> int:
    # a number the graph's values decide, each container and object counted once
    if x is None:
        return 7
    if isinstance(x, bool):
        return 3 if x else 5
    if isinstance(x, int):
        return x % 1000003
    if isinstance(x, float):
        return int(x * 8) % 1000003
    if isinstance(x, str):
        return len(x) * 31 + 1
    k = id(x)
    if k in seen:
        return 1
    seen[k] = True
    total = 11
    if isinstance(x, list) or isinstance(x, tuple):
        for item in x:
            total = (total * 17 + checksum(item, seen)) % 1000003
    elif isinstance(x, dict):
        for key in x:
            total = (total * 19 + checksum(key, seen) * 3 + checksum(x[key], seen)) % 1000003
    elif isinstance(x, Node):
        total = (total + checksum(x.payload, seen) + checksum(x.children, seen) * 5 + checksum(x.parent, seen) + len(x.label)) % 1000003
    elif isinstance(x, Leaf):
        total = (total + checksum(x.value, seen) * 7) % 1000003
    elif isinstance(x, Pair):
        total = (total + checksum(x.left, seen) * 13 + checksum(x.right, seen)) % 1000003
    elif isinstance(x, Counter):
        total = (total + checksum(x.count, seen)) % 1000003
    elif isinstance(x, Registry):
        total = (total + checksum(x.entries, seen) * 23) % 1000003
    elif isinstance(x, Event):
        total = (total + checksum(x.data, seen) * 29 + len(x.kind)) % 1000003
    return total


g = build(3)
c = copy_value(g, {})
print(text(g) == text(c))
print(text(c)[:400])
print(c is g, c.children[0] is g.children[0], c.children[0].parent is c, c.children[0].payload is c.children[2].payload)
print(c.children[0].payload is not g.children[0].payload, c.children[3].left is c.children[3].right)
reg = c.children[4]
print(reg.entries["self"] is reg, reg.entries[("child", 1)] is c.children[1], type(reg.entries[1.5]).__name__)
c.children[0].payload.append("only in the copy")
print(len(g.children[0].payload), len(c.children[0].payload), len(c.children[2].payload))
print(c.payload["counter"].count, g.payload["counter"].count, build(2).payload["counter"].count)
total = 0
for seed in range(1, 6):
    gs = build(seed)
    total += checksum(copy_value(gs, {}), {})
print(total)
