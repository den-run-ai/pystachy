# typing.Final annotations: Final[T] is T, Final alone takes the value's type.
from typing import Final
import typing
from mods.finalerr import ParseError as IniError

X: Final = 3
Y: Final[int] = 4
Z: typing.Final[str] = "z"


class C:
    K: Final = 2.5
    name: Final[str]

    def __init__(self, n: str) -> None:
        self.name = n
        self.size: Final = len(n)


class ParseError(Exception):
    path: Final[str]

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.path = path


def f() -> int:
    w: Final = 7
    return w + X + Y


c = C("abc")
print(X, Y, Z, c.K, c.name, c.size, f())
try:
    raise ParseError("a.ini")
except ParseError as e:
    print(e.path, repr(e))
try:
    raise IniError("c.ini", 1, "bad")
except IniError as e:
    print(e, repr(e), e.path, e.lineno, e.msg)
raise ParseError("b.ini")
