# None == None also where one operand is an object of a class with subclasses and the other a
# value of another type that may be None (a str | None, a list, a boxed int, a tuple or a dict):
# CPython compares the two None objects, which are one. Each other pair is never equal
class Node:
    pass


class Leaf(Node):
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Leaf)


class Other:
    pass


class More(Other):
    pass


def text(o: Node | None, s: str | None) -> tuple[bool, bool, bool, bool]:
    return (o == s, o != s, s == o, s != o)


def items(o: Node | None, n: list[int] | None) -> tuple[bool, bool, bool, bool]:
    return (o == n, n == o, o != n, n != o)


def number(o: Node | None, i: int | None, f: float | None) -> tuple[bool, bool, bool, bool]:
    return (o == i, i != o, o == f, f != o)


def pair(o: Node | None, t: tuple[int, str] | None, d: dict[str, int] | None) -> tuple[bool, bool, bool, bool]:
    return (o == t, t != o, o == d, d != o)


def unrelated(o: Node | None, p: Other | None) -> tuple[bool, bool, bool, bool]:
    return (o == p, o != p, p == o, p != o)


print(text(None, None), text(Leaf(), None), text(None, "x"), text(Node(), "x"))
print(items(None, None), items(Leaf(), None), items(None, [1]), items(Node(), []))
print(number(None, None, None), number(Node(), None, None), number(None, 0, 0.0), number(Leaf(), 1, 1.5))
print(pair(None, None, None), pair(Leaf(), None, None), pair(None, (1, "a"), {"k": 1}))
print(unrelated(None, None), unrelated(Node(), None), unrelated(None, More()), unrelated(Leaf(), Other()))
