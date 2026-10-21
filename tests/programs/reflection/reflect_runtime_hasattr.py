# hasattr(o, name) with a name read at run time (#489): the name's index in the name table of the
# exact class's reflection record; a field __init__ may leave unassigned reads its flag, a
# property runs its getter (AttributeError: False); a slot no code assigns is no attribute
class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        if x > 5:
            self.z = 9

    def norm(self) -> int:
        return self.x * self.x + self.y * self.y

    @property
    def scaled(self) -> int:
        if self.x > 3:
            raise AttributeError("too big")
        return self.x * 10


class Slots:
    __slots__ = ("a", "b")

    def __init__(self) -> None:
        self.a = 1


class Base:
    def __init__(self) -> None:
        self.base = 1


class Derived(Base):
    def __init__(self) -> None:
        super().__init__()
        self.derived = 2


class Cat:
    def meow(self) -> str:
        return "meow"


class Dog:
    def woof(self) -> str:
        return "woof"


names = input().split()
p = Point(1, 2)
q = Point(7, 1)
s = Slots()
for name in names:
    print(name, hasattr(p, name), hasattr(q, name), hasattr(s, name))
objs: list[Base] = [Base(), Derived()]
pets: list[Cat | Dog] = [Cat(), Dog()]
for name in ["base", "derived", "meow", "woof", "__dict__", "__slots__"]:
    n = name + ""
    print(n, [hasattr(o, n) for o in objs], [hasattr(x, n) for x in pets], hasattr(None, n), hasattr(1, n), hasattr("s", n))
