# A module that opts in to dynamic Any reads its classes as typed class objects (#7), and keeps
# the class boxes it made of them before, Any values, where the program does not compile with
# typed ones: a list or a set of classes that a builtin class joins, a variable that holds a class
# and then another value, a dict of classes that takes a builtin class as a key.
# pystachy: dynamic-any
from typing import Any


class A:
    tag = "a"

    def __init__(self, v: int = 1) -> None:
        self.v = v

    def hi(self) -> str:
        return "hi" + str(self.v)


class A2(A):
    tag = "a2"


class B:
    tag = "b"

    def __init__(self, v: int = 2) -> None:
        self.v = v


def made(flag: bool) -> None:
    k = A2 if flag else A
    print(k.__name__, k is A, k == A2)
    k = "no class"
    print(k)


made(True)
made(False)
ks = [A, A2]
ks.append(str)
ks.append(B)
print(ks, len(ks), ks[0] is A, ks[2] is str)
s = {A, A2}
s.add(int)
print(len(s), A in s, int in s, B in s)


def rebound() -> None:
    k = A
    i = 0
    while i < 3:
        print(k)
        k = B if i == 0 else int
        i += 1


rebound()
o = B()
t = type(o)
print(t, t is B)
t = type(1)
print(t, t is int)
d = {A: "a", A2: "a2"}
d[float] = "f"
x: Any = A2()
print(d[A], d[float], d.get(type(x), "none"), len(d))
