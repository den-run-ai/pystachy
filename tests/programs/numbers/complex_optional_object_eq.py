# == and != of a complex | None and an object | None whose class's __eq__ takes a complex number:
# two None values are equal, by identity, in either order; None and an object, or None and a
# complex number, are not; a complex number and an object ask the object's __eq__
class Match:
    def __eq__(self, other: complex) -> bool:
        return True


def number(flag: bool) -> complex | None:
    return 1j if flag else None


def match(flag: bool) -> Match | None:
    return Match() if flag else None


for fx in [False, True]:
    for fy in [False, True]:
        x = number(fx)
        y = match(fy)
        print(fx, fy, x == y, y == x, x != y, y != x)
