"""@overload stubs that no def follows (a function's, methods'): CPython keeps them, and a call of one raises NotImplementedError."""
from typing import overload


@overload
def pick(x: int) -> int: ...


def other(x: int) -> int:
    return x + 1


class Pair:
    def __init__(self, a: int, b: int) -> None:
        self.a = a
        self.b = b

    @overload
    def scaled(self, k: int) -> int: ...

    @overload
    @staticmethod
    def make(a: int) -> int: ...

    def total(self) -> int:
        return self.a + self.b
