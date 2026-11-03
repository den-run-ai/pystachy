# An enum class's lookup by value finds a member held through a base class's type (Enum, or the
# enum class's own base) as CPython does: Color(x) returns it, and x in Color is True; a member of
# another class is no member (CPython's ValueError and False)
from enum import Enum


class Color(Enum):
    RED = 1
    GREEN = 2


class Shade(Enum):
    DARK = 1


class Base(Enum):
    def label(self) -> str:
        return self.name.lower()


class Size(Base):
    SMALL = 1


def reparse(x: Enum) -> Color:
    return Color(x)


def has(x: Enum) -> bool:
    return x in Color


def resize(x: Base) -> Size:
    return Size(x)


print(reparse(Color.RED) is Color.RED)
print(has(Color.GREEN), has(Shade.DARK))
e: Enum = Color.GREEN
print(Color(e), e in Color)
try:
    print(reparse(Shade.DARK))
except ValueError as err:
    print("ValueError", err)
print(resize(Size.SMALL), resize(Size.SMALL).label())
