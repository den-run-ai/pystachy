# An enum class's __init__ may precede the members in the class body, as its other methods may:
# it is called for each member all the same (the members are made once the body has run)
from enum import Enum, IntEnum


class Planet(Enum):
    def __init__(self, mass, radius):
        self.mass = mass
        self.radius = radius

    def gravity(self) -> float:
        return 6.67300E-11 * self.mass / (self.radius * self.radius)

    MERCURY = (3.303e+23, 2.4397e6)
    EARTH = (5.976e+24, 6.37814e6)
    TERRA = (5.976e+24, 6.37814e6)


class Level(IntEnum):
    def __init__(self, n: int) -> None:
        self.label = "L%d" % n
        print("made", self.name, n)

    LOW = 1
    HIGH = 2


print(list(Planet), Planet.TERRA is Planet.EARTH, round(Planet.MERCURY.gravity(), 2), Planet.EARTH.mass)
print(Level.LOW.label, Level.HIGH.label, Level(2), Level.HIGH + 1)
