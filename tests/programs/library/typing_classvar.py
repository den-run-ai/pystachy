# x: ClassVar[T] = v in an ordinary class is the class attribute x: T = v (once rejected).
from typing import ClassVar


class Counter:
    instances: ClassVar[int] = 0

    def __init__(self) -> None:
        self.n = 1


print(Counter().n)
