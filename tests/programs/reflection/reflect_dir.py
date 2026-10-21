# dir(o) of a statically known class (#486): a new sorted list of the names its objects answer
# to; loops over it (or sorted(dir(o))) unroll, and tests of the name's literal fold in each copy
from dataclasses import dataclass


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def norm(self) -> int:
        return self.x * self.x + self.y * self.y

    @property
    def size(self) -> int:
        return 2

    @staticmethod
    def make() -> int:
        return 1

    @classmethod
    def build(cls) -> int:
        return 2


class Slots:
    __slots__ = ("a", "b")

    def __init__(self) -> None:
        self.a = 1


class Annotated:
    count: int

    def __init__(self) -> None:
        self.count = 0


class Base:
    def base_m(self) -> int:
        return 1


class Derived(Base):
    def __init__(self) -> None:
        self.d = 1

    def derived_m(self) -> int:
        return 2


@dataclass
class Item:
    name: str
    qty: int = 0


class MyTests:
    def test_add(self) -> None:
        print("add ok", 1 + 1 == 2)

    def test_mul(self) -> None:
        print("mul ok", 2 * 3 == 6)

    def helper(self) -> None:
        print("not a test")


print([n for n in dir(Point(1, 2)) if not n.startswith("_")])
print(dir(Point(1, 2)))
print(dir(Slots()))
print([n for n in dir(Annotated()) if n.startswith("__a")])
xs: list[Base] = [Base(), Derived()]
for x in xs:
    print([n for n in dir(x) if not n.startswith("_")])
print(dir(Item("pen")))
print(len(dir(1)), dir("s")[-3:], dir([1])[-4:], dir(None)[:2])
t = MyTests()
for name in sorted(dir(t)):
    if name.startswith("test_"):
        getattr(t, name)()
for name in dir(t):
    if name.endswith("_mul") or name == "helper":
        print("found", name)
