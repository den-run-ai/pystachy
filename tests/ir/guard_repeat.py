# One guard message repeated many times in one function: every check of a possibly-None
# receiver and every overflow check jumps to the one cold block of its message.
class Node:
    def __init__(self, v: int, nxt: "Node | None") -> None:
        self.v = v
        self.nxt = nxt


def total(a: Node | None, b: Node | None) -> int:
    s = a.v + b.v
    s = s + a.v * b.v
    s = s - a.v - b.v
    s = s * 2 + a.v
    if s > 10:
        s = s + b.v * 3
    return s * a.v + b.v


def walk(n: Node | None) -> int:
    t = 0
    while n is not None:
        t = t + n.v * n.v
        n = n.nxt
    return t


x = Node(3, Node(4, None))
print(total(x, x.nxt), walk(x))
