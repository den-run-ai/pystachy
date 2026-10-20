# pystachy: dynamic-any
"""Dynamic-Any boxing and dispatch costs; CPU time for construction and scanning excludes startup.

Build once, then alternate the modes, each with the same N:
  typed N    list[int], summed into an int
  union N    list[int | str], narrowed with isinstance(), summed into an int
  dyn N      list[Any], narrowed with isinstance(), summed into an int
  generic N  list[Any], summed into an Any (each addition dispatches and boxes its result)
  graph N    the heterogeneous object graph of tests/programs/inference/dynany_graph.py: N graphs built, then each
             deep-copied and checksummed through its Any values
Each prints a checksum, the construction CPU nanoseconds and the processing CPU nanoseconds.
Use PYSTACHY_GC=stats in a separate untimed run to report the heap peak (docs/dynamic-any.md).
"""
import sys
from time import process_time_ns
from typing import Any, Callable


def typed(n: int) -> None:
    start = process_time_ns()
    values: list[int] = []
    for i in range(n):
        values.append(i)
    built = process_time_ns()
    total = 0
    for value in values:
        total += value
    end = process_time_ns()
    print(total, built - start, end - built)


def union(n: int) -> None:
    start = process_time_ns()
    values: list[int | str] = []
    for i in range(n):
        values.append(i)
    built = process_time_ns()
    total = 0
    for value in values:
        if isinstance(value, int):
            total += value
    end = process_time_ns()
    print(total, built - start, end - built)


def dyn(n: int) -> None:
    start = process_time_ns()
    values: list[Any] = []
    for i in range(n):
        values.append(i)
    built = process_time_ns()
    total = 0
    for value in values:
        if isinstance(value, int):
            total += value
    end = process_time_ns()
    print(total, built - start, end - built)


def generic(n: int) -> None:
    start = process_time_ns()
    values: list[Any] = []
    for i in range(n):
        values.append(i)
    built = process_time_ns()
    total: Any = 0
    for value in values:
        total += value
    end = process_time_ns()
    print(total, built - start, end - built)


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


class Registry:
    def __init__(self) -> None:
        self.entries: dict[Any, Any] = {}


class Event:
    def __init__(self, kind: str, data: Any) -> None:
        self.kind = kind
        self.data = data


def copy_value(x: Any, memo: dict[int, Any]) -> Any:
    if x is None or isinstance(x, bool) or isinstance(x, int) or isinstance(x, float) or isinstance(x, str):
        return x
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


def build(seed: int) -> Any:
    root = Node("root", seed)
    shared: list[Any] = [seed, "shared", seed * 0.5]
    counter = Counter()
    counter.count = seed % 3 if seed % 2 == 0 else str(seed)
    reg = Registry()
    for i in range(3):
        child = Node("c" + str(i), shared if i % 2 == 0 else (i, str(i), None))
        child.parent = root
        child.children.append(Leaf(i * seed))
        child.children.append(Pair(child, counter))
        root.children.append(child)
        reg.entries[("child", i)] = child
        reg.entries[i * 1.5] = Event("made", [child.label, i, True])
    root.children.append(Pair(shared, shared))
    root.children.append(reg)
    reg.entries["self"] = reg
    reg.entries[None] = Leaf({"deep": [reg, root, {"k": (1, 2.0, "x")}]})
    root.payload = {"seed": seed, "counter": counter, "flags": [True, False, None]}
    return root


def checksum(x: Any, seen: dict[int, bool]) -> int:
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


def graph(n: int) -> None:
    start = process_time_ns()
    graphs: list[Any] = []
    for seed in range(n):
        graphs.append(build(seed))
    built = process_time_ns()
    total = 0
    for g in graphs:
        total = (total + checksum(copy_value(g, {}), {})) % 1000003
    end = process_time_ns()
    print(total, built - start, end - built)


mode = sys.argv[1]
n = int(sys.argv[2])
assert n > 0 and n <= 10000000
if mode == "typed":
    typed(n)
elif mode == "union":
    union(n)
elif mode == "dyn":
    dyn(n)
elif mode == "generic":
    generic(n)
else:
    graph(n)
