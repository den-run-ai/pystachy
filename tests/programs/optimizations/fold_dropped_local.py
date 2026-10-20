# A name that a function binds only in code dropped at compile time (a Windows branch, an import
# under "if TYPE_CHECKING:") is still its local, as in CPython: a read of it raises
# UnboundLocalError where the read runs. A list comprehension's own variable and an annotation are
# not such reads.
import sys
from typing import TYPE_CHECKING
from loader.shapes import Square

x = 5


def never() -> None:
    if sys.platform == "win32":
        x = 1
    print(x)


def f(flag: bool) -> int:
    if sys.platform == "win32":
        x = -1
    if flag:
        return x
    return 0


def g() -> list[int]:
    if sys.platform == "win32":
        x = 1
    return [x * 2 for x in range(3)]


def area(s: Square) -> int:
    if TYPE_CHECKING:
        from loader.shapes import Square
    t: Square = s
    return t.n * t.n


def h() -> str:
    if sys.platform.startswith("win"):
        name: str = "nt"
    print("before")
    return name


print(f(False), g(), area(Square(3)), x)
print(h())
