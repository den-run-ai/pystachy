"""Takes mods.star_base's names with import *, then rebinds some of them, as socket rebinds
_socket's getaddrinfo and socket, and signal its getsignal (decorated)."""
import mods.star_base as _base
from mods.star_base import *


def shout(name: str) -> str:
    return greet(name).upper()  # (it runs only once the def below has rebound greet)


class Error(_base.Error):
    pass


class Shape(_base.Shape):
    def area(self) -> int:
        return 10 * self.n

    def twice(self) -> "Shape":
        return Shape(2 * self.n)


def _keep(f):
    print("decorated")
    return f


@_keep
def greet(name: str) -> str:
    return "over hello " + name + ", " + _base.greet(name)
