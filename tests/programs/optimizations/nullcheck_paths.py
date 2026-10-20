# A read through None raises AttributeError where CPython raises it, on every path, though the
# nullcheck pass (#787) drops the checks that a passed test of the same value makes redundant:
# a read after an if that may skip the first, after a loop or comprehension that may not run,
# after a try whose handler goes on, of a variable assigned again, of a parameter a closure
# assigns, and after a yield. log shows where each call got before it raised.
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


def resumed(a: Node | None):
    yield a.v
    log.append("resumed")
    yield a.v + a.v


x = Node(3, Node(4, None))
for k in range(16):
    log.clear()
    try:
        if k == 0:
            print(one_branch(x, True), one_branch(x, False), zero_trips(x, 2), comprehension(x, 3), handled(x))
        elif k == 1:
            print(reassigned(x, x), tested(x), tested(None), list(resumed(x)))
        elif k == 2:
            print(one_branch(None, True))
        elif k == 3:
            print(one_branch(None, False))
        elif k == 4:
            print(zero_trips(None, 0))
        elif k == 5:
            print(zero_trips(None, 2))
        elif k == 6:
            print(comprehension(None, 0))
        elif k == 7:
            print(comprehension(None, 2))
        elif k == 8:
            print(handled(None))
        elif k == 9:
            print(reassigned(x, None))
        elif k == 10:
            print(reassigned(None, x))
        elif k == 11:
            print(written(x))
        elif k == 12:
            print(list(resumed(None)))
        elif k == 13:
            g = resumed(x)
            print(next(g))
            print(next(g))
        else:
            print(written(None) if k == 14 else tested(Node(1, None)))
    except AttributeError as e:
        print(k, "AttributeError:", e, log)
