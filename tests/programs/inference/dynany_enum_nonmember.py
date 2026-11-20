# pystachy: dynamic-any
# nonmember() values that the class body binds after members, in a module that opts in to dynamic
# Any, read through the members (P.A.G, self.G) as CPython's members read the class attribute:
# numbers too, whose members' fields share the class's boxes.
from enum import Enum, IntEnum, nonmember


class P(Enum):
    A = 1
    B = 2
    G = nonmember(7)
    R = nonmember(2.5)
    T = nonmember(True)
    S = nonmember("s")
    PAIR = nonmember((1, 2.5))
    C = 3
    H = nonmember(G + 1)

    def scaled(self) -> int:
        return self.value * self.G

    @nonmember
    def ratio(self) -> float:
        return self.value * self.R


class Q(IntEnum):
    X = 1
    STEP = nonmember(10)
    Y = 2

    def next(self) -> int:
        return self + self.STEP


print(P.A.G, P.B.G, P.C.G, P.A.R, P.A.T, P.A.S, P.A.PAIR, P.C.H, P.G, P.H)
print(P.B.scaled(), P.C.ratio(), [p.scaled() for p in P])
print(Q.X.STEP, Q.Y.next(), Q.STEP)
