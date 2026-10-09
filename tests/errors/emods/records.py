"""A NamedTuple that Pystachy cannot compile: an error only where the program uses it."""
from typing import NamedTuple


class Untyped(NamedTuple):
    a: int

    def f(self, x):
        return x


class Fine(NamedTuple):
    a: int
