# A tuple's in, count() and index() compare an object of a union of classes as one of its member's
# class: by its __eq__, also reflected, else by identity, and as None where the union holds None
# (#1432). The same object is found first, as CPython's PyObject_RichCompareBool finds it, also a
# file's, which compares by identity alone.
import io
from typing import TextIO


class C:
    def __init__(self, n: int) -> None:
        self.n = n


class E:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, E) and other.n == self.n


def search(x: C | E, y: C | E) -> None:
    print(x in (y,), y in (x,), (x, y).count(y), (y, x).index(x), x in (x,))


def maybe(x: C | E | None, y: C | E | None) -> None:
    print(x in (y,), (x, y).count(y), None in (x,), (y,).count(None))


def plain(x: C | E, e: E, c: C) -> None:
    print(e in (x,), x in (e,), (x, c).count(c), c in (x,), x in (1, "s"))


def files(f: TextIO | io.StringIO, g: TextIO | io.StringIO) -> None:
    print(f in (f,), f in (g,), (f, g).count(g))


c = C(1)
search(E(1), E(1))
search(E(1), E(2))
search(c, c)
search(c, C(1))
search(c, E(1))
maybe(None, None)
maybe(E(3), None)
maybe(E(3), E(3))
plain(E(4), E(4), c)
plain(c, E(4), c)
a = io.StringIO("a")
files(a, io.StringIO("b"))
files(a, a)
