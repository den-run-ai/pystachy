# The first assignment of a global that a template's function reads before its module's code
# assigns it: a value that calls a function assigning the global itself (as a read of the
# global in its own first assignment does), an if a static test decides (only the branch that
# runs counts, also for a fill), a comprehension, and a, b = ... unpacking.
import sys


def setg() -> None:
    global G
    G = 2


setg()
G = G * 2
print(G)


class Box:
    def __init__(self, v: int):
        self.v = v


def pair() -> tuple[int, str]:
    return 4, "q"


def show(x):
    return f"{x} {H} {K * 2} {L} {SQUARES} {EVENS} {LO}{HI} {A}{B} {C}{D} {P}{Q}"


def init(x):
    global H
    H = x
    return x


if len(sys.argv) > 3:
    print(show(1))
H = init(5)
V = 3
if isinstance(V, str):
    K = "s"
elif V is None:
    K = "none"
else:
    K = 5
L = []
if not isinstance(V, int):
    L.append("s")
else:
    L.append(V)
LIMIT = 3
SQUARES = [i * i for i in range(4)]
EVENS = [i for i in range(10) if i % 2 == 0 and i < LIMIT * 2]
LO, HI = 1, "x"
A, B = pair()
C, D = [7, 8], "zw"
P, Q = "ab"
print(show(2))


def keep(x):
    out = []
    if isinstance(x, str):
        out = [x]
    return out


print(keep("a"), keep(1))
