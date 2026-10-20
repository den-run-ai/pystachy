# TYPE_CHECKING = False as humanize, prettytable and msgpack spell it (tests/programs/optimizations/fold_false.py): the
# imports and the class under its test are never loaded or compiled.
from __future__ import annotations

TYPE_CHECKING = False

if TYPE_CHECKING:
    import pathlib
    from typing import Protocol

    class Sized(Protocol):
        def get(self) -> int: ...

if not TYPE_CHECKING:
    MODE = "runtime"


def mode() -> str:
    if TYPE_CHECKING:
        return "checking"
    return MODE


def local() -> bool:
    TYPE_CHECKING = True  # (the function's own)
    return TYPE_CHECKING


class Box:
    def __init__(self, n: int):
        self.n = n

    def get(self) -> int:
        return self.n
