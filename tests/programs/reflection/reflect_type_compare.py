# type(a) is C, type(a) == type(b) and their negations (#486): the records of the exact types
# compared, which LLVM folds where the static types decide
class Point:
    def __init__(self, x: int) -> None:
        self.x = x


class Base:
    pass


class Derived(Base):
    pass


class Other:
    pass


a = Point(1)
b = Point(2)
print(type(a) is Point, type(a) == type(b), type(a) is not Point, type(a) != type(b))
print(type(a) is Other, a.__class__ is Point, type(a) == Point)
xs: list[Base] = [Base(), Derived()]
for x in xs:
    print(type(x) is Base, type(x) is Derived, type(x) == type(xs[0]), type(x) != type(xs[1]))
mixed: list[Point | Other] = [Point(3), Other()]
for m in mixed:
    print(type(m) is Point, type(m) is Other, type(m) == type(mixed[1]))
print(type(1) is int, type(True) is int, type(True) is bool, type("s") == str, type([1]) is list)
print(type([1]) == type(["a"]), type({1: 2}) is dict, type((1,)) is tuple, type(1.0) is float)
n: int | str = 5
print(type(n) is int, type(n) is str, type(n) == type("x"))
o: Point | None = None
print(type(o) is Point, type(o) is type(None))
