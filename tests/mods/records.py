"""NamedTuple classes of a module: names qualified, one that Pystachy cannot compile unused."""
import typing as t
from typing import NamedTuple


class Pos(t.NamedTuple):
    line: int
    col: int = 0

    def moved(self, by: int) -> "Pos":
        return self._replace(col=self.col + by)


class Token(NamedTuple):
    kind: str
    text: str | None
    at: Pos


class Untyped(NamedTuple):
    a: int

    def f(self, x):
        return x
