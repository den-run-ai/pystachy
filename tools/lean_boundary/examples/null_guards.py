# Null-check Lean corpus fixture: branches, loops, mutation and exceptions.
# Adapted from tests/programs/optimizations/nullcheck_paths.py; generators remain
# explicitly unsupported by the current normalized model.
class Node:
    def __init__(self, v: int, nxt: "Node | None") -> None:
        self.v = v
        self.nxt = nxt


log: list[str] = []


def one_branch(a: Node | None, c: bool) -> int:
    t = 0
    if c:
        log.append("then")
        t = a.v
    log.append("after")
    return t + a.v + a.v


def zero_trips(a: Node | None, n: int) -> int:
    t = 0
    for i in range(n):
        log.append(f"trip {i}")
        t += a.v + a.v
    log.append("after")
    return t + a.v


def comprehension(a: Node | None, n: int) -> int:
    xs = [a.v for _ in range(n)]
    log.append("after")
    return len(xs) + a.v


def handled(a: Node | None) -> int:
    x = 0
    try:
        x = a.v
    except AttributeError:
        log.append("handler")
        x = -1
    log.append("after")
    return x + a.v


def reassigned(a: Node | None, b: Node | None) -> int:
    x = a
    t = x.v
    log.append("again")
    x = b
    return t + x.v + x.v


def written(a: Node | None) -> int:
    def clear() -> None:
        nonlocal a
        a = None

    t = a.v
    clear()
    log.append("cleared")
    return t + a.v


def tested(n: Node | None) -> int:
    t = 0
    while n is not None:
        t += n.v * 10 + n.v
        n = n.nxt
    return t



x = Node(3, Node(4, None))
print(one_branch(x, True), zero_trips(x, 2), comprehension(x, 3), handled(x))
print(reassigned(x, x), tested(x), tested(None))
