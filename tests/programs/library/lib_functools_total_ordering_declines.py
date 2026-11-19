# functools.total_ordering of a class whose own method returns NotImplemented: the methods
# added return it too, so that the other operand's reflected method runs, then TypeError,
# which names the operator the program wrote.
from functools import total_ordering
from typing import Optional


@total_ordering
class Version:
    def __init__(self, major: int, minor: int) -> None:
        self.major = major
        self.minor = minor

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor) == (other.major, other.minor)

    def __lt__(self, other: object) -> bool:
        print("Version.__lt__")
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor) < (other.major, other.minor)

    def __hash__(self) -> int:
        return hash((self.major, self.minor))


class Loose:
    def __init__(self, n: int) -> None:
        self.n = n

    def __le__(self, other):
        print("Loose.__le__")
        if isinstance(other, Version):
            return self.n <= other.major
        return NotImplemented

    def __gt__(self, other):
        print("Loose.__gt__")
        if isinstance(other, Version):
            return self.n > other.major
        return NotImplemented


vs = [Version(1, 2), Version(1, 10), Version(0, 9), Version(1, 2)]
for a in vs[:2]:
    for b in vs:
        print(a < b, a <= b, a > b, a >= b, a == b, a != b)
print([f"{v.major}.{v.minor}" for v in sorted(vs)], max(vs).minor, min(vs).minor)
lo = [Loose(1), Loose(5)]
for x in lo:
    # Version's methods decline a Loose: its reflected ones answer where it has them
    print(vs[0] >= x)
    print(vs[0] < x)
    for op in ["<=", ">"]:
        try:
            print(vs[0] <= x if op == "<=" else vs[0] > x)
        except TypeError as e:
            print("TypeError", e)


def cmp(a: Version, b: Optional[Version]) -> None:
    for op in ["<", "<=", ">", ">="]:
        try:
            if op == "<":
                print(a < b)
            elif op == "<=":
                print(a <= b)
            elif op == ">":
                print(a > b)
            else:
                print(a >= b)
        except TypeError as e:
            print("TypeError", e)


cmp(vs[0], vs[1])
cmp(vs[0], None)
for other in [3]:
    try:
        print(vs[0] >= other)
    except TypeError as e:
        print("TypeError", e)
    try:
        print(vs[0] <= other)
    except TypeError as e:
        print("TypeError", e)
