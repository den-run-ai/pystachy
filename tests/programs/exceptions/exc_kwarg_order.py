# A call of an exception class evaluates all its arguments, keyword ones too, in order before it
# makes the object: what str() and repr() show of a positional argument is what it holds once a
# keyword argument has run, and a keyword argument that raises leaves no object made.
from typing import Callable


class E(Exception):
    def __init__(self, xs: list[int], k: int):
        pass


class D(Exception):
    def __init__(self, xs: list[int], k: int = 5, *, m: list[int] = []):
        print("D.__init__", xs, k, m)


class S(Exception):
    def __init__(self, xs: list[int], k: int):
        super().__init__(xs, k)


class Loud:
    def __repr__(self) -> str:
        print("repr Loud")
        return "Loud()"


class L(Exception):
    def __init__(self, o: Loud, k: int):
        print("L.__init__")


class F(Exception):
    def __init__(self, msg: str, m: list[float], cb: Callable[[int], int], o: int | None = None):
        super().__init__(msg)
        self.m = m
        self.cb = cb
        self.o = o


class G(F):
    pass


class O(OSError):
    def __init__(self, code: int, *, why: str):
        print("O.__init__", code, why)
        super().__init__(code, why)


def update(xs: list[int]) -> int:
    xs.append(len(xs) + 1)
    return len(xs)


def arg(tag: str, v: int) -> int:
    print("arg", tag)
    return v


def boom() -> int:
    raise ValueError("boom")


xs = [1]
error = E(xs, k=update(xs))
print(error, repr(error), xs)
print(E(xs, k=0), E([arg("p", 1)], k=arg("k", 2)))
d = D(xs, m=[update(xs)])
print(d, repr(d), xs)
d = D(xs, k=update(xs))
print(d, xs)
d = D([arg("a", 1)], arg("b", 2), m=[arg("m", 3)])
print(d)
s = S(xs, k=update(xs))
print(s, xs)

try:
    raise E(xs, k=update(xs))
except E as e:
    print("raised", e, repr(e), xs)
try:
    raise D([arg("a", 1)], k=arg("k", 2), m=[arg("m", 3), update(xs)])
except D as e:
    print("raised", e, xs)
try:
    raise O(arg("code", 2), why="no " + str(arg("why", 3)))
except OSError as e:
    print("raised", e)

# a keyword argument that raises: nothing of the call that would make the object runs
try:
    e2 = E([], k=boom())
    print("not reached", e2)
except ValueError as x:
    print("caught", x)
try:
    e3 = L(Loud(), k=boom())
    print("not reached", e3)
except ValueError as x:
    print("caught", x)
try:
    raise L(Loud(), k=boom())
except ValueError as x:
    print("caught", x)
except L:
    print("not reached")

# the keyword arguments get their parameters' types
flag = True
f = F("a", m=[1.0, 2.0], cb=lambda x: x + 1, o=3 if flag else None)
print(f, f.m, f.cb(1), f.o)
g = G("b", cb=lambda x: x * 2, m=[float(update(xs))])
print(g, g.m, g.cb(4), g.o, xs)
