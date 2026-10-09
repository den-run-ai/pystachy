"""A class whose @overload stubs no def follows: CPython keeps each, and a call of one raises NotImplementedError."""
import typing as t
from typing import overload


class Pair:
    def __init__(self, a: int, b: int) -> None:
        self.a = a
        self.b = b

    @overload
    def scaled(self, k: int) -> int: ...

    @t.overload
    def __eq__(self, o: object) -> bool: ...

    @overload
    @staticmethod
    def make(a: int) -> int: ...

    @overload
    def total(self, k: int) -> int: ...

    def size(self) -> int:
        return 2

    def total(self, k: int = 0) -> int:
        return self.a + self.b + k
