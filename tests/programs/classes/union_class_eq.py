# == and != of a value of a union of classes (A | B) and an object compare the object the union
# holds: by identity where the classes define no __eq__, and by the __eq__ of its class where one
# does, as CPython compares the object itself.
class Base:
    def __init__(self, n: int) -> None:
        self.n = n


class A(Base):
    pass


class B(Base):
    pass


class E(Base):
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Base) and other.n == self.n


def same(x: A | B, y: Base) -> bool:
    return x == y


def differ(x: A | B, y: Base) -> bool:
    return x != y


def same_any(x: A | E, y: object) -> bool:
    return x == y


a = A(1)
b = B(7)
print(same(b, b), same(a, b), differ(b, b), differ(a, b))
print(same_any(a, a), same_any(a, A(1)), same_any(E(3), B(3)), same_any(E(3), B(4)))
