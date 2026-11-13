# An enum class's ordering method that returns NotImplemented for another class's member.
from enum import Enum


class Level(Enum):
    LOW = 1
    HIGH = 2

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


class Color(Enum):
    RED = 1


ls = [Level.HIGH, Level.LOW]
print(ls[0] < ls[1], ls[1] < ls[0], sorted(ls)[0].name, min(ls).name, Level.LOW < Level.HIGH)
for other in [Color.RED]:
    try:
        print(ls[0] < other)
    except TypeError as e:
        print("TypeError", e)
