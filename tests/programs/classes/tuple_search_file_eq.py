# A tuple's in, count() and index() with a union of a file and a class's objects: a file is found
# by identity, and an object of a class on the other side by its __eq__ too, which CPython calls
# once the file's declines (main ran this; the union search must keep it)
import sys
from typing import TextIO


class Q:
    pass


class E:
    def __eq__(self, other: object) -> bool:
        return True


class N:
    def __eq__(self, other: object) -> bool:
        return False


def f(x: TextIO | Q, y: E) -> None:
    print(y in (x,), x in (y,), (x,).count(y), (y,).count(x), (x, y).index(y), (y, x).index(x))


def g(x: TextIO | Q, y: N) -> None:
    print(y in (x,), x in (y,), (x,).count(y), (x, x).count(x))


def h(x: TextIO | Q, y: TextIO | Q) -> None:
    print(x in (y,), (y, x).count(x))


f(sys.stdout, E())
f(Q(), E())
g(sys.stdout, N())
g(Q(), N())
h(sys.stdout, sys.stderr)
h(sys.stdout, sys.stdout)
h(Q(), sys.stdout)
