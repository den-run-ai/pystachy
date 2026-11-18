# error: enum class Base's __init__() is not supported: the class that defines the members defines it
# CPython calls an __init__ that an enum class without members defines for the members of the
# classes deriving from it (printing 1)
from enum import Enum


class Base(Enum):
    def __init__(self, x: int) -> None:
        self.x = x


class C(Base):
    A = 1


print(C.A.x)
