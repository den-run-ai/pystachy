# complex | C compares member by member: complex numbers by value, an object by its class's __eq__
# (also reflected, for a complex number, whose __eq__ declines an object), else by identity.
class C:
    def __init__(self, n: int) -> None:
        self.n = n


class Loose:
    def __eq__(self, other: object) -> bool:
        print("Loose.__eq__")
        return True


class Sub(C):
    pass


class Plain:
    pass


def eq(x: complex | C, y: complex | C) -> None:
    print(x == y, y == x, x != y, x in (y,))


def loose(x: complex | Loose, y: complex | Loose) -> None:
    print(x == y, y == x, x != y, x in (y,))


def maybe(x: complex | C | None, y: complex | C | None) -> None:
    print(x == y, x != y, x == None, y in (x,))


def plain(x: complex | Plain, y: complex | Plain) -> None:
    print(x == y, y == x, x != y, x in (y,))


c = C(1)
eq(2j, 2j)
eq(2j, 1 + 2j)
eq(2j, c)
eq(c, c)
eq(c, C(1))
eq(Sub(2), c)
loose(Loose(), 2j)
loose(2j, Loose())
loose(1j, 1j)
maybe(None, None)
maybe(None, 2j)
maybe(c, None)
maybe(1j, 1j)
maybe(c, c)
p = Plain()
plain(p, p)
plain(p, Plain())
plain(1j, p)
plain(1j, 1j)
