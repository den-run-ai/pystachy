# An enum class's __init__ gives its members attributes: EnumType calls it for each member, once
# the member has its name and value, with the items of the value (a tuple's, else the value), in
# the order of the class body; an alias's too, whose object it then drops for the member of that
# value. A parameter without an annotation takes the type of its item
from enum import Enum, IntEnum, StrEnum, unique


class Planet(Enum):
    MERCURY = (3.303e+23, 2.4397e6)
    VENUS = (4.869e+24, 6.0518e6)
    EARTH = (5.976e+24, 6.37814e6)

    def __init__(self, mass, radius):
        self.mass = mass
        self.radius = radius

    @property
    def surface_gravity(self) -> float:
        return 6.67300E-11 * self.mass / (self.radius * self.radius)

    def heavier(self, other: "Planet") -> bool:
        return self.mass > other.mass


@unique
class Color(Enum):
    RED = ("r", 255, 0, 0)
    GREEN = ("g", 0, 128, 0)

    def __init__(self, key: str, r: int, g: int, b: int = 7) -> None:
        self.key = key
        self.rgb = (r, g, b)
        self.label: str = self.name.title() + "/" + str(self.value[1])

    def hex(self) -> str:
        return "#%02x%02x%02x" % self.rgb


class Level(Enum):
    LOW = 1
    HIGH = 2
    TOP = 2

    def __init__(self, n):
        print("init", self.name, n)
        self.weight = n * 10


class Nested(Enum):
    A = ("a", (1, 2))
    B = ("b", (3, 4))

    def __init__(self, tag, pair):
        self.tag = tag
        self.total: int = pair[0] + pair[1]


class Word(Enum):
    HI = "hello"
    YO = "yo"

    def __init__(self, text):
        self.size = len(text)


for p in Planet:
    print(p.name, p.value, p.mass, f"{p.surface_gravity:.2f}", p.heavier(Planet.MERCURY))
print(Planet((5.976e+24, 6.37814e6)) is Planet.EARTH, Planet["VENUS"].radius, Planet.EARTH)
print([(c.key, c.rgb, c.label, c.hex()) for c in Color], Color(("g", 0, 128, 0)).key)
print(Level.TOP is Level.HIGH, Level.TOP.weight, [(m.name, m.weight) for m in Level], Level(1).weight)
print([(n.tag, n.total) for n in Nested], [(w.name, w.size) for w in Word], Word("yo").size)
Level.LOW.weight = 99
print(Level.LOW.weight, Level(1).weight)


class Code(IntEnum):
    OK = 200
    MISSING = 404

    def __init__(self, n):
        self.group = n // 100


class Unit(StrEnum):
    METRE = "m"
    SECOND = "s"

    def __init__(self, symbol):
        self.shown = "[" + symbol + "]"


print(Code.OK.group, Code(404).group, Code.MISSING + 1, Unit.METRE.shown, Unit("s").shown, Unit.SECOND + "!")
