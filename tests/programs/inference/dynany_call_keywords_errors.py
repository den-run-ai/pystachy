# pystachy: dynamic-any
# Keyword arguments that do not fit, through Any values (#774): CPython's TypeError, raised once
# the method is found and the arguments are evaluated, and a missing method's AttributeError
# before they are.
from typing import Any


class C:
    def m(self, a: int, b: int = 0) -> int:
        return a + b

    def only(self, a: int, /, b: int = 0) -> int:
        return a + b

    def kwo(self, a: int, *, flag: bool) -> int:
        return a if flag else -a


def g(a: int, b: int = 0) -> int:
    return a * b


def make(n: int) -> Any:
    def add(x: int, y: int = 1) -> int:
        return n + x + y

    return add


def side(s: str) -> int:
    print("evaluated", s)
    return 1


def attempt(what: str, x: Any) -> None:
    try:
        if what == "unexpected":
            print(x.m(1, zzz=side("zzz")))
        elif what == "multiple":
            print(x.m(side("a"), a=side("a again")))
        elif what == "missing":
            print(x.m(b=2))
        elif what == "positional-only":
            print(x.only(a=1, b=2))
        elif what == "keyword-only":
            print(x.kwo(1))
        elif what == "too many":
            print(x.kwo(1, 2, flag=True))
        elif what == "bound method":
            f: Any = x.m
            print(f(1, 2, b=3))
        elif what == "function":
            h: Any = g
            print(h(1, c=side("c")))
        elif what == "closure":
            add: Any = make(10)
            print(add(1, z=2))
        elif what == "closure positional":
            add2: Any = make(10)
            print(add2(1, 2, 3))
        elif what == "lambda":
            lam: Any = lambda a, b=1: a + b
            print(lam(1, c=2))
        elif what == "absent":
            print(x.nope(1, k=side("k")))
        elif what == "sort":
            xs: Any = [3, 1]
            print(xs.sort(cmp=side("cmp")))
        else:
            ys: Any = [3, 1]
            print(ys.sort(reverse="yes"))
    except (TypeError, AttributeError) as e:
        print(what, type(e).__name__ + ":", e)


x: Any = C()
for w in ["unexpected", "multiple", "missing", "positional-only", "keyword-only", "too many", "bound method", "function", "closure", "closure positional", "lambda", "absent", "sort", "reverse"]:
    attempt(w, x)
