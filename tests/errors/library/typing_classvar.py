# error: typing_classvar.py:6: error: typing.ClassVar (a class attribute) is not supported
from typing import ClassVar


class Counter:
    instances: ClassVar[int] = 0

    def __init__(self) -> None:
        self.n = 1


print(Counter().n)
