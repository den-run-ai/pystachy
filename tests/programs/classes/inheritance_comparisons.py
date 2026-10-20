# A strict subtype on the right gets the first reflected comparison, including equality.
# Methods guard None because comparisons are allowed to pass it to user-defined protocols.
class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: "Base | None") -> bool:
        print("Base.eq")
        return other is not None and self.n == other.n

    def __ne__(self, other: "Base | None") -> bool:
        print("Base.ne")
        return other is None or self.n != other.n

    def __lt__(self, other: "Base | None") -> bool:
        print("Base.lt")
        return other is not None and self.n < other.n

    def __gt__(self, other: "Base | None") -> bool:
        print("Base.gt")
        return other is not None and self.n > other.n

    def __le__(self, other: "Base | None") -> bool:
        print("Base.le")
        return other is not None and self.n <= other.n

    def __ge__(self, other: "Base | None") -> bool:
        print("Base.ge")
        return other is not None and self.n >= other.n


class Child(Base):
    def __eq__(self, other: Base | None) -> bool:
        print("Child.eq")
        return other is not None and self.n % 10 == other.n % 10

    def __ne__(self, other: Base | None) -> bool:
        print("Child.ne")
        return other is None or self.n % 10 != other.n % 10

    def __lt__(self, other: Base | None) -> bool:
        print("Child.lt")
        return other is not None and self.n % 10 < other.n % 10

    def __gt__(self, other: Base | None) -> bool:
        print("Child.gt")
        return other is not None and self.n % 10 > other.n % 10

    def __le__(self, other: Base | None) -> bool:
        print("Child.le")
        return other is not None and self.n % 10 <= other.n % 10

    def __ge__(self, other: Base | None) -> bool:
        print("Child.ge")
        return other is not None and self.n % 10 >= other.n % 10


def compare(a: Base, b: Base) -> None:
    print(a == b, a != b, a < b, a > b, a <= b, a >= b)


print(Base(2) == Child(12), Base(2) != Child(12))
print(Base(2) <= Child(12), Base(2) >= Child(12))
compare(Base(3), Child(12))
compare(Child(12), Base(3))
compare(Base(2), Base(3))
compare(Child(12), Child(13))
items: list[Base] = [Base(2), Child(2)]
print(items.count(Child(12)))
item: Base = Child(2)
print(item == None, None == item, item != None, None != item)
print(item < None, None > item, item > None, None < item)


class Plain:
    pass


class Ordered(Plain):
    def __lt__(self, other: Plain) -> bool:
        return True

    def __gt__(self, other: Plain) -> bool:
        return False


def less(a: Plain, b: Plain) -> bool:
    return a < b


print(less(Ordered(), Plain()), less(Plain(), Ordered()))
try:
    print(less(Plain(), Plain()))
except TypeError as e:
    print("TypeError:", e)
