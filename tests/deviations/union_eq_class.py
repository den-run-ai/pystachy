# == of two values of a union that holds a class whose __eq__ takes only its own class (as
# annotated): CPython calls Node.__eq__ with the int as well, which raises AttributeError here;
# Pystachy, which cannot call it with an int, raises TypeError. So it does for a class whose
# __eq__ takes no value of its own class (CPython calls Odd.__eq__, which returns True), and for
# one whose __eq__ has no annotation, which Pystachy compiles for its own class's values only
class Node:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: "Node") -> bool:
        return self.name == other.name


def same(a: Node | int, b: Node | int) -> bool:
    return a == b


print(same(Node("a"), Node("a")), same(1, 1), same(1, 2), same(Node("a"), Node("b")))
try:
    print(same(Node("a"), 1))
except TypeError as e:
    print("TypeError:", e)


class Odd:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: int) -> bool:
        return True


class Loose:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other) -> bool:
        return self.n == other.n


def odd(k: int) -> Odd | str:
    return Odd(k) if k > 0 else "s"


def loose(k: int) -> Loose | str:
    return Loose(k) if k > 0 else "s"


print(odd(0) == odd(0), loose(2) == loose(2), loose(2) == loose(3), loose(0) == loose(0))
try:
    print(odd(1) == odd(2))
except TypeError as e:
    print("TypeError:", e)
try:
    print(loose(1) == loose(0))
except TypeError as e:
    print("TypeError:", e)
