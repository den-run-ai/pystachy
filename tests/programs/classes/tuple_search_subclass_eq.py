# A tuple's in, count() and index() call the __eq__ of an object's runtime class, as == does
# (#1430): an object typed as its base class finds an int or a str that its subclass's __eq__
# finds equal, in either position. A subclass whose __eq__ takes another type is not called with
# this one, which its body would find not equal; one without __eq__ compares identity.
class Base:
    pass


class Loose(Base):
    def __eq__(self, other: object) -> bool:
        return (isinstance(other, int) and other == 1) or (isinstance(other, str) and other == "one")


class IntMatch(Base):
    def __eq__(self, other: int) -> bool:
        return other == 1


class StrMatch(Base):
    def __eq__(self, other: str) -> bool:
        return other == "one"


def make(n: int) -> Base:
    if n == 1:
        return IntMatch()
    if n == 2:
        return StrMatch()
    if n == 3:
        return Loose()
    return Base()


def search(x: Base) -> None:
    print(x in (1,), 1 in (x,), x in ("one",), "one" in (x,), x in (2.5,))
    print((x, 1, x).count(1), ("one", x).count("one"), (2.5, x).count(2.5))
    try:
        print((2, x).index(1), ("two", x).index("one"))
    except ValueError as e:
        print("ValueError:", e)


for n in range(4):
    search(make(n))
