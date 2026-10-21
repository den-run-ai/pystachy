# The text of getattr(o, name[, default]) with a name read at run time (#489's first version):
# print(), str(), repr() and f-strings of what CPython's lookup finds, per exact class: a
# field's or property's value, a bound method, an object's own attributes; the default for a
# name the object does not have, else CPython's AttributeError
class Point:
    """A point."""

    kind = "pt"

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        if x > 5:
            self.z = 9

    def __repr__(self) -> str:
        return f"Point({self.x}, {self.y})"

    def norm(self) -> int:
        return self.x * self.x + self.y * self.y

    @property
    def scaled(self) -> int:
        if self.x > 3:
            raise AttributeError("too big")
        return self.x * 10

    @classmethod
    def origin(cls) -> int:
        return 0


class Base:
    def __init__(self) -> None:
        self.a = "aa"

    def f(self) -> int:
        return 1

    def __repr__(self) -> str:
        return "Base()"


class Derived(Base):
    def __init__(self) -> None:
        super().__init__()
        self.b = 2.5


def arg(tag: str) -> str:
    print("arg", tag)
    return tag


names = input().split()
p = Point(1, 2)
for name in names:
    print(name, getattr(p, name, -1), repr(getattr(p, name, None)))
print(str(getattr(Point(7, 1), names[1])), f"[{getattr(p, names[0])}]")
print(getattr(p, names[2]), arg("after"))
objs: list[Base] = [Base(), Derived()]
for o in objs:
    for n in ["a", "b", "f", "__module__", "__doc__", "__class__", "__dict__", "zz"]:
        nn = n + ""
        print(nn, getattr(o, nn, None))
try:
    print(getattr(p, names[-1]))
except AttributeError as e:
    print("AttributeError:", e)
try:
    print(getattr(Point(4, 4), "scaled" + ""))
except AttributeError as e:
    print("AttributeError:", e)
