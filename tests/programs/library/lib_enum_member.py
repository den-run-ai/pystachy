# member() and nonmember() in an enum class body, whose namespace unwraps the value: member(v)
# makes the member of value v, nonmember(v) a class attribute that holds v, which the class, its
# members and the members after it read (C = B + 1), and @nonmember a method. A = B = value
# binds each name in turn (B is A's alias, also for one auto()). @enum.property, and @property
# of from enum import property, is a property of the members.
import enum
from enum import Enum, IntEnum, StrEnum, auto, member, nonmember, property


class Planet(Enum):
    MERCURY = 1
    VENUS = member(2)
    G = nonmember(7)
    UNIT = nonmember("km")
    PAIR = nonmember((1, 2.5))
    EARTH = member(auto())

    @enum.property
    def lower(self) -> str:
        return self.name.lower()

    @nonmember
    def weight(self) -> int:
        return self.value * self.G

    @property
    def label(self) -> str:
        return self.lower + "/" + self.UNIT


class Count(IntEnum):
    A = 1
    B = nonmember(2)
    C = B + 1
    D = member(B * 5)
    E = F = 10
    G = H = auto()


class Color(StrEnum):
    RED = ROJO = auto()
    GREEN = "g"
    SHADE = nonmember("dark")


print(list(Planet), len(Planet), Planet.G, Planet.UNIT, Planet.PAIR, Planet.EARTH.G, Planet.VENUS.UNIT)
print(Planet.MERCURY.lower, Planet.VENUS.weight(), Planet.EARTH.label, Planet(3), Planet["EARTH"], "G" in Planet.__members__)
print(list(Count), Count.B, Count.C, Count(10), Count.F is Count.E, Count.H, list(Count.__members__))
print(list(Color), Color.ROJO is Color.RED, Color.SHADE, Color.GREEN.SHADE, member(3).value, nonmember("x").value)
