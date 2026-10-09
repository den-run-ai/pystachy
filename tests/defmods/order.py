# Def and class statements run in order with the module's other code. The default values
# Pystachy compiles may read names bound in a loop, a with block or a branch: they are checked
# when they run. The class bodies it leaves uncompiled may compute with builtin values, and
# what a base class names is the class statement that ran before.
import os
import sys
import typing

for LIMIT in range(3):
    pass
while True:
    STEP = 2
    break
with open("tests/defmods/order.py") as fh:
    FIRST = fh.readline()
if sys.maxsize > 2:
    TOP = 5
else:
    raise SystemExit
if len(sys.argv) > 0:
    SIZE: int = 3
X = 0
if len(sys.argv) > 5:
    pass
else:
    del X
    X = 2


def total(a: int, k: int = LIMIT, s: int = STEP, t: int = TOP, n: int = SIZE, x: int = X) -> int:
    return a + k + s + t + n + x


def first(line: str = FIRST) -> str:
    return line.strip()


class A:
    pass


class A(A):
    pass


class B:
    pass


class C(B):
    pass


class B(C):
    pass


class Hooked:
    pass


class Mid(Hooked):
    "the Hooked above, whose subclasses run no __init_subclass__"


class Hooked:
    def __init_subclass__(cls, **kw):
        print("hook", cls.__name__)


class Base[T]:
    pass


class Box[T](Base[T]):
    pass


class Desc:
    def __init__(self) -> None:
        self.n = 0

    def __get__(self, obj: object, typ: object) -> int:
        return 1


class Holder:
    "CPython calls Desc.__get__ only where the attribute is read"
    x: Desc = Desc()


class Consts:
    MAX = 2**31 - 1
    MASK = 1 << 4
    t = typing.Optional[int]
    j = os.path.join
    out = sys.stdout.write
    s = "abc".upper()
    D = dict(a=1)
    a, b = 1, 2
    n = 1
    n += 1
    tmp = 1
    del tmp
    if sys.version_info >= (3, 8):
        V = 1
    else:
        V = 2
    if sys.maxsize > 0:

        def g(self, *a):
            pass

    @staticmethod
    def go(x, *a):
        return x


@typing.final
@object.__new__
class SENTINEL:
    pass


staticmethod = 5
print("defmods.order: loaded", staticmethod)
