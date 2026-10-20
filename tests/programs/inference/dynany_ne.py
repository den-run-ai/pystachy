# pystachy: dynamic-any
# != of Any objects runs __ne__ where the class or a subclass defines it, with a strict
# subclass's first, as CPython does, and otherwise inverts __eq__; a container's search still
# runs only __eq__.
from typing import Any


class E:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: object) -> bool:
        print("E.eq")
        return isinstance(other, E) and self.v == other.v

    def __ne__(self, other: object) -> bool:
        print("E.ne")
        return True


class F(E):
    def __ne__(self, other: object) -> bool:
        print("F.ne")
        return False


class G(E):
    pass


class P:
    def __init__(self, v: int) -> None:
        self.v = v


class Q(P):
    def __ne__(self, other: object) -> bool:
        print("Q.ne")
        return False


class H:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: object) -> bool:
        print("H.eq")
        return isinstance(other, H) and self.v == other.v


def main() -> None:
    e: Any = E(1)
    f: Any = F(1)
    g: Any = G(1)
    print(e != f, f != e, e != g, g != e, e != e)
    p: Any = P(1)
    q: Any = Q(1)
    print(p != q, q != p, p != p)
    h1: Any = H(1)
    h2: Any = H(1)
    h3: Any = H(2)
    print(h1 != h2, h1 != h3, h1 == h2)
    xs: list[Any] = [e, f, g]
    print(xs.count(e), e in xs)


main()
