# error: enum class Pair's __init__() is not supported: the compiler makes and looks up its members
# CPython calls both the __new__ and the __init__ of an enum class for each member (printing 3)
from enum import Enum


class Pair(Enum):
    A = (1, 2)

    def __new__(cls, a, b):
        obj = object.__new__(cls)
        obj.first = a
        return obj

    def __init__(self, a, b):
        self.total = a + b


print(Pair.A.total)
