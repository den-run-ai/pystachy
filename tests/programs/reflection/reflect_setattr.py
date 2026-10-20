# setattr(o, "name", value) with a name the compiler knows (#486): o.name = value, with o and
# value evaluated first; a property's setter, __slots__ and frozen dataclasses as for o.name = v
from dataclasses import FrozenInstanceError, dataclass


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


class Temp:
    def __init__(self) -> None:
        self._c = 0.0

    @property
    def celsius(self) -> float:
        return self._c

    @celsius.setter
    def celsius(self, v: float) -> None:
        print("setter", v)
        self._c = v


class Slotted:
    __slots__ = ("a",)

    def __init__(self) -> None:
        self.a = 1


@dataclass(frozen=True)
class Frozen:
    x: int


def obj(tag: str) -> Point:
    print("object", tag)
    return Point(0, 0)


def val(tag: str) -> int:
    print("value", tag)
    return 5


p = Point(1, 2)
setattr(p, "x", 10)
setattr(p, "y", getattr(p, "y") * 10)
print(p.x, p.y)
setattr(obj("a"), "x", val("a"))
t = Temp()
setattr(t, "celsius", 21.5)
print(t.celsius)
s = Slotted()
setattr(s, "a", 7)
print(s.a)
f = Frozen(1)
try:
    setattr(f, "x", 2)
except FrozenInstanceError as e:
    print("FrozenInstanceError:", e)
print(f.x)
