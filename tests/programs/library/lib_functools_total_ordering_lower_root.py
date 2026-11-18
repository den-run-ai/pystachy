# functools.total_ordering of classes that inherit an ordering method below the greatest of
# those their body defines (__lt__, then __le__, __gt__ and __ge__): CPython's decorator computes
# the missing ones from the body's (A's __lt__, C's __le__) and keeps the inherited one.
from functools import total_ordering


class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Base) and self.n == other.n

    def __gt__(self, other: "Base") -> bool:
        print("Base.__gt__")
        return self.n > other.n * 10


@total_ordering
class A(Base):
    def __lt__(self, other: "Base") -> bool:
        print("A.__lt__")
        return self.n < other.n


class Base2:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Base2) and self.n == other.n

    def __ge__(self, other: "Base2") -> bool:
        print("Base2.__ge__")
        return False


@total_ordering
class C(Base2):
    # (__le__ is the greatest root: __lt__ and __gt__ are computed from it, __ge__ stays Base2's)
    def __le__(self, other: "Base2") -> bool:
        print("C.__le__")
        return self.n <= other.n


a, b = A(1), A(2)
print(a < b)
print(a <= b)
print(a > b)
print(a >= b)
print(b > a, A(30) > a)
c, d = C(1), C(2)
print(c < d)
print(c <= d)
print(c > d)
print(c >= d)
print(c < c, c > c, sorted([d, c])[0].n)
