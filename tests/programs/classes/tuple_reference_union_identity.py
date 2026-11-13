import io
import sys
from typing import TextIO


class A:
    pass


class B:
    pass


class Derived(A):
    pass


def search(x: A | B, y: A | B) -> None:
    xs = (y, y)
    print(x in xs, x not in xs, xs.count(x))
    try:
        print(xs.index(x))
    except ValueError:
        print("absent")


def concrete(x: A, y: A | B) -> None:
    print(x in (y,), y in (x,), (y,).count(x), (x,).count(y))
    if x is y:
        print((y,).index(x), (x,).index(y))


def derived(x: Derived | B, y: A | B) -> None:
    print(x in (y,), y in (x,), (y,).count(x), (x,).count(y))
    if x is y:
        print((y,).index(x), (x,).index(y))


def optional(x: A | B | None) -> None:
    print(None in (x,), x in (None,), (x,).count(None), (None,).count(x))
    if x is None:
        print((x,).index(None), (None,).index(x))


def files(x: TextIO | io.StringIO, y: TextIO | io.StringIO) -> None:
    print(x in (y,), x not in (y,), (y, y).count(x))
    if x in (y,):
        print((y,).index(x))


def file_concrete(x: TextIO, y: TextIO | io.StringIO) -> None:
    print(x in (y,), y in (x,), (y,).count(x), (x,).count(y))
    if x in (y,):
        print((y,).index(x), (x,).index(y))


a = A()
b = B()
d = Derived()
search(a, a)
search(a, A())
search(a, b)
search(b, b)
search(None, None)
search(None, a)
search(a, None)
concrete(a, a)
concrete(a, A())
concrete(None, None)
derived(d, d)
derived(d, a)
optional(None)
optional(a)
f = io.StringIO("one")
files(f, f)
files(f, io.StringIO("two"))
files(sys.stdout, sys.stdout)
files(sys.stdout, f)
files(f, sys.stdout)
file_concrete(sys.stdout, sys.stdout)
file_concrete(sys.stdout, f)
