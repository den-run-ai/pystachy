import copy
from enum import Enum, IntEnum, StrEnum, auto, unique


class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3
    CRIMSON = 1

    def describe(self) -> str:
        return f"{self.name} is {self.value}"


print(Color.RED, repr(Color.RED), Color.RED.name, Color.RED.value, Color.RED._name_, Color.RED._value_)
print(Color(2), Color["BLUE"], Color.CRIMSON is Color.RED, Color(Color.GREEN))
print(list(Color), len(Color), Color.RED in Color, 2 in Color, 5 in Color)
print(Color)
for c in Color:
    print(c.describe())
print(Color.__members__)
try:
    Color(7)
except ValueError as e:
    print("ValueError", e)
try:
    Color["PURPLE"]
except KeyError as e:
    print("KeyError", e)
print(f"{Color.GREEN}", f"{Color.GREEN:>12}|", hash(Color.RED) == hash("RED"), str(Color.BLUE))
print(Color.RED == Color.RED, Color.RED == Color.GREEN, Color.RED != Color.BLUE, Color.RED is Color.CRIMSON)
d = {Color.RED: "r", Color.GREEN: "g"}
print(d[Color.CRIMSON], sorted(Color, key=lambda c: -c.value), list(Color)[::-1])
print(copy.copy(Color.RED) is Color.RED, copy.deepcopy([Color.RED])[0] is Color.RED)
print(isinstance(Color.RED, Color), isinstance(Color.RED, Enum), type(Color.RED).__name__)


# auto(): one more than the greatest value before (from 1)
class Order(Enum):
    A = auto()
    B = 5
    C = auto()
    D = 3
    E = auto()


print([(m.name, m.value) for m in Order], Order.__members__["C"])


# methods, properties and tuple values; an enum class without members as a base
class Body(Enum):
    def describe(self) -> str:
        return "<" + self.name + ">"


class Planet(Body):
    MERCURY = (3.303e+23, 2.4397e6)
    VENUS = (4.869e+24, 6.0518e6)

    @property
    def mass(self) -> float:
        return self.value[0]

    @classmethod
    def lightest(cls) -> "Planet":
        return Planet.MERCURY


print(Planet.VENUS.describe(), Planet.MERCURY.mass, Planet((4.869e+24, 6.0518e6)), Planet.lightest())
print(isinstance(Planet.VENUS, Body), [p.name for p in Planet])


class Level(Enum):
    LOW = 0.5
    HIGH = 2.5


print(Level(2.5), Level.LOW.value, list(Level))


class Num(IntEnum):
    ONE = 1
    TWO = 2
    ZERO = 0


print(Num.ONE, repr(Num.TWO), Num.ONE + 1, Num.TWO * 3, Num.TWO - Num.ONE, Num.TWO // 2, Num.TWO / 4)
print(Num.ONE == 1, Num.ONE != 2, Num.ONE < Num.TWO, Num.TWO >= 2, Num.ONE.value, f"{Num.TWO:03d}")
print(bool(Num.ZERO), bool(Num.ONE), -Num.TWO, hash(Num.TWO) == hash(2), sorted([Num.TWO, Num.ZERO]))
try:
    print(Num.ONE + "x")
except TypeError as e:
    print("TypeError", e)
x: Num | None = None
try:
    print(x < Num.ONE)
except TypeError as e:
    print("TypeError", e)


class Mode(StrEnum):
    READ = auto()
    WRITE = "w"


print(Mode.READ, repr(Mode.WRITE), Mode.READ == "read", Mode.WRITE.upper(), Mode.READ + "!", len(Mode.READ))
print(f"[{Mode.WRITE}]", "ea" in Mode.READ, Mode.READ.startswith("re"), Mode("w"), Mode.WRITE < "x")
try:
    print(Mode.READ < 3)
except TypeError as e:
    print("TypeError", e)


@unique
class Planet2(Enum):
    MERCURY = 1
    VENUS = 2


print(Planet2.VENUS, len(Planet2))
