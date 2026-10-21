# A function compiled in the middle of another's compile is compiled as it would be on its own
# (#822): inner(P) is compiled while outer unrolls its loop over 17 attribute names. inner's own
# unrolled loop is within the budget of copies, as it is when inner is compiled first.
class P:
    def __init__(self):
        self.a0 = 0
        self.a1 = 1
        self.a2 = 2
        self.a3 = 3
        self.a4 = 4
        self.a5 = 5
        self.a6 = 6
        self.a7 = 7
        self.a8 = 8
        self.a9 = 9
        self.a10 = 10
        self.a11 = 11
        self.a12 = 12
        self.a13 = 13
        self.a14 = 14
        self.a15 = 15
        self.a16 = 16


def inner(o):
    s = 0
    for name in ("a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8", "a9", "a10", "a11", "a12", "a13", "a14", "a15", "a16"):
        s += getattr(o, name)
    return s


def outer(o: P) -> int:
    t = 0
    for name in ("a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8", "a9", "a10", "a11", "a12", "a13", "a14", "a15", "a16"):
        t += getattr(o, name) + inner(o)
    return t


print(outer(P()))
