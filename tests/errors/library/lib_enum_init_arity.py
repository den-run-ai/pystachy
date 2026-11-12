# error: C.__init__() takes 2 positional arguments but 3 were given
# CPython raises this TypeError where the class statement makes the member
from enum import Enum


class C(Enum):
    A = (1, 2)

    def __init__(self, x: int) -> None:
        self.x = x


print(C.A.x)
