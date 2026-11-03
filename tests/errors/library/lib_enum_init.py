# error: enum class C's __init__() is not supported: the compiler makes and looks up its members
# CPython calls __init__ with each member's value (printing 1)
from enum import Enum


class C(Enum):
    A = (1, 2)

    def __init__(self, x: int, y: int) -> None:
        self.x = x


print(C.A.x)
