"""A module with TypeVars: its functions that mention one are templates (names qualified)."""
from typing import TypeVar

from typing_extensions import TypeVar as XTypeVar

_T = TypeVar("_T")
_D = XTypeVar("_D", covariant=True)


def get(d: dict[str, _T], key: str, default: _D) -> "_T | _D":
    return d[key] if key in d else default


def pair(a: _T, b: _T) -> tuple[_T, _T]:
    return (a, b)


class Box:
    def __init__(self, v: int) -> None:
        self.v = v

    def get(self, default: _D) -> int:
        return self.v
