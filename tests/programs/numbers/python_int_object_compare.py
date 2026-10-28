# pystachy: python-int
# Promoting ints (docs/python-int.md) compared with objects whose comparison methods take an int:
# a method takes a 64-bit int as the promoting int its parameter is, and an int past 64 bits as it
# is, where an object is compared with an int and where x in t, t.count(x) and t.index(x) compare
# a tuple's items with x (the item's __eq__(x), or x's __eq__(item)). A class of a module that
# does not opt in takes the ints as 64-bit ints, and objects without the methods (object(), a
# range) equal no int.
from fixed_compare import Fixed, FixedOrder


class OnlyInts:
    def __eq__(self, other: int) -> bool:
        print("  eq", other)
        return other == 3


class Ord:
    def __init__(self, x: int) -> None:
        self.x = x

    def __lt__(self, other: int) -> bool:
        print("  lt", other)
        return self.x < other

    def __ge__(self, other: int) -> bool:
        print("  ge", other)
        return self.x >= other


class Base:
    def __eq__(self, other: int) -> bool:
        print("  Base.eq", other)
        return other == 1


class Sub(Base):
    def __eq__(self, other: int) -> bool:
        print("  Sub.eq", other)
        return other == 2 ** 70


class Plain:
    pass


def pick(i: int) -> Base:
    return Base() if i == 0 else Sub()


big = 2 ** 70
n = 3
m = n + 0
t = (1, n)
u = (1, big)
# an object == an int, also a tuple's item
print(OnlyInts() == 3, OnlyInts() == n, OnlyInts() == m, OnlyInts() != 4, OnlyInts() == t[1])
print(OnlyInts() == big, OnlyInts() != big, OnlyInts() == u[1], OnlyInts() == -big)
# <, >=, and the reflected methods of an int < an object
print(Ord(5) < 7, Ord(5) < n, Ord(5) >= t[0], Ord(5) < big, Ord(5) >= u[1])
print(7 > Ord(5), n <= Ord(5), big > Ord(5), -big <= Ord(5))
# a subclass's method, by the object's class
print(pick(0) == 1, pick(1) == 1, pick(0) == big, pick(1) == big)
# x in t, t.count(x) and t.index(x)
print(OnlyInts() in (1, 3), OnlyInts() in t, OnlyInts() in u, OnlyInts() not in (1, 2))
print(3 in (OnlyInts(),), m in (OnlyInts(),), big in (OnlyInts(),), big in (Sub(), 1), 1 in (pick(0),))
print(t.count(OnlyInts()), u.count(OnlyInts()), (1, 2, 3).index(OnlyInts()), (big, m).index(OnlyInts()))
try:
    print((1, big).index(OnlyInts()))
except ValueError as e:
    print("ValueError:", e)
maybe: OnlyInts | None = None
print(maybe == m, maybe != big)
maybe = OnlyInts()
print(maybe == m, maybe == big)
# objects without comparison methods
print(1 in (Plain(),), big in (Plain(), 1), object() == big, object() != m, range(3) == big, big != range(3))
# a class of a module that does not opt in
print(Fixed() == 3, Fixed() == m, Fixed() in t, m in (Fixed(),), t.count(Fixed()))
print(FixedOrder(5) < 7, FixedOrder(5) >= m, 7 > FixedOrder(5), m <= FixedOrder(5))
