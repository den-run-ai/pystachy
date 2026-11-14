import typing
from typing import Literal
from typing import Literal as L


def mode(x: L[L["r"], L["w"]]) -> str:
    return x


def repeat(x: Literal[Literal["a"], typing.Literal["b"]], n: typing.Literal[typing.Literal[1], 2] = 1) -> str:
    return x * n


def flag(x: Literal[Literal[True], Literal[Literal[False]]]) -> bool:
    return not x
