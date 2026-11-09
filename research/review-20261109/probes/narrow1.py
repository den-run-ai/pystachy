import sys


def run(label: str, f) -> None:
    try:
        print(label, f())
    except Exception as e:
        print(label, type(e).__name__, e)


def n1(flag: bool) -> str:
    x: str | None = "a"

    def clear() -> None:
        nonlocal x
        x = None

    if x is not None:
        if flag:
            clear()
        return x.upper()
    return "none"


def n2(xs: list[str | None]) -> int:
    t = 0
    for x in xs:
        if x is None:
            continue
        t += len(x)
    return t


def n3(v: int | None, w: int | None) -> int:
    if v is None or w is None:
        return -1
    return v + w


def n4(v: int | str | None) -> str:
    if isinstance(v, int):
        return "int" + str(v + 1)
    if v is None:
        return "none"
    return "str" + v.upper()


def n5(flag: bool) -> int:
    x: list[int] | None = [1, 2]

    def clear() -> None:
        nonlocal x
        x = None

    if x:
        if flag:
            clear()
        return len(x)
    return -1


def n6(flag: bool) -> int:
    x: int | None = 5
    holder: list[int | None] = [x]

    def clear() -> None:
        nonlocal x
        x = None

    while x is not None:
        if flag:
            clear()
        return x + 1
    return -1


def n7(d: dict[str, int], k: str) -> int:
    v = d.get(k)
    if v is None:
        v = 0
    for i in range(3):
        if i == 1:
            v = d.get("missing")
        if v is None:
            return -5
        v += 1


def n8(a: str | None, b: str | None) -> str:
    c = a or b
    if c is None:
        return "?"
    d = a and b
    return c + (d if d is not None else "-")


def n9(x: float | None) -> float:
    y = x
    if y is None:
        y = 1.5
    else:
        y = y * 2
    return y


def n10(xs: list[int] | None, flag: bool) -> int:
    if xs is None:
        xs = []
    if flag:
        xs = None
    try:
        return len(xs)
    except TypeError as e:
        return -7


class Node:
    def __init__(self, v: int, nxt: "Node | None") -> None:
        self.v = v
        self.nxt = nxt


def n11(n: Node | None) -> int:
    t = 0
    while n is not None:
        t += n.v
        n = n.nxt
    return t


def n12(n: Node | None) -> int:
    if n is not None and n.nxt is not None and n.nxt.nxt is None:
        return n.nxt.v
    return -1


def n13(n: Node) -> int:
    m = n.nxt
    if m is None:
        return 0
    n.nxt = None
    m2 = n.nxt
    return m.v + (m2.v if m2 is not None else 100)


def main(z: int) -> None:
    run("n1f", lambda: n1(False))
    run("n1t", lambda: n1(True))
    run("n2", lambda: n2(["a", None, "bcd"]))
    run("n3", lambda: (n3(1, 2), n3(None, 2), n3(1 + z, None)))
    run("n4", lambda: (n4(1), n4(None), n4("x")))
    run("n5f", lambda: n5(False))
    run("n5t", lambda: n5(True))
    run("n6f", lambda: n6(False))
    run("n6t", lambda: n6(True))
    run("n7", lambda: (n7({"a": 1}, "a"), n7({"missing": 4}, "x")))
    run("n8", lambda: (n8("a", "b"), n8(None, "b"), n8("", None), n8("", ""), n8(None, None)))
    run("n9", lambda: (n9(None), n9(2.0), n9(0.0)))
    run("n10", lambda: (n10(None, False), n10([1], False), n10([1], True)))
    run("n11", lambda: n11(Node(1, Node(2, Node(3 + z, None)))))
    run("n12", lambda: (n12(Node(1, Node(2, None))), n12(Node(1, None)), n12(None)))
    run("n13", lambda: (n13(Node(1, Node(2, None))), n13(Node(1, None))))


main(len(sys.argv) - 1)
