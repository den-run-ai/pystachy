from typing import Optional


class Base:
    def __init__(self, n: int) -> None:
        self.n = n
        self.calls: list[str] = []

    def __eq__(self, other):
        print("Base.__eq__", type(self).__name__, type(other).__name__)
        if not isinstance(other, Base):
            return NotImplemented
        return self.n == other.n

    def __lt__(self, other):
        print("Base.__lt__", type(self).__name__, type(other).__name__)
        if not isinstance(other, Base):
            return NotImplemented
        return self.n < other.n

    def __hash__(self) -> int:
        return hash(self.n)


class Sub(Base):
    def __eq__(self, other):
        print("Sub.__eq__", type(self).__name__, type(other).__name__)
        if not isinstance(other, Sub):
            return NotImplemented
        return super().__eq__(other) and True

    def __gt__(self, other):
        print("Sub.__gt__", type(self).__name__, type(other).__name__)
        if not isinstance(other, Sub):
            return NotImplemented
        return self.n > other.n

    def __hash__(self) -> int:
        return hash(self.n)


class Other:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other):
        print("Other.__eq__", type(other).__name__)
        if isinstance(other, Base):
            return self.n == other.n
        return NotImplemented

    def __gt__(self, other):
        print("Other.__gt__", type(other).__name__)
        if isinstance(other, Base):
            return self.n > other.n
        return NotImplemented


def show(x: Base, y: Base) -> None:
    print(x == y, x != y, x < y)


b1 = Base(1)
b2 = Base(2)
s1 = Sub(1)
s2 = Sub(2)
show(b1, b2)
show(b1, s1)
show(s1, b1)
show(s1, s2)
print(b1 < s2, s2 > b1, s1 > s2)
o = Other(1)
print(b1 == o, o == b1, b1 != o, b1 < o, s1 == o)
print(o == Other(1), o != Other(1))
try:
    print(o > Other(2))
except TypeError as e:
    print("TypeError", e)
try:
    print(o < b1)
except TypeError as e:
    print("TypeError", e)


def opt(x: Optional[Base], y: Optional[Base]) -> None:
    print(x == y, x != y)
    try:
        print(x < y)
    except TypeError as e:
        print("TypeError", e)


opt(b1, None)
opt(None, b1)
opt(None, None)
opt(s1, b2)
ys: list[Base] = [s2, b1, Base(0)]
d: dict[Base, str] = {b1: "one", s2: "two"}
print(d[Base(1)], d[Sub(2)], Base(2) in d, len(set(ys)))
print(sorted(ys)[0].n)
