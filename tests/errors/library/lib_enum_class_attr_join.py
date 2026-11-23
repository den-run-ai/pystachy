# error: returns both EnumType
import sys
from enum import Enum


class A(Enum):
    LOW = 1


class B(Enum):
    LOW = 2


class Registry:
    first = A
    second = B

    def choose(self, flag: bool):
        if flag:
            return self.first
        return self.second


flag = len(sys.argv) > 5
print(Registry().choose(flag).LOW)
