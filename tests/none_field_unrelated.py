# A field first None, where a method of an unrelated class stores the same attribute name. A
# store to that class's own object (self.value = 1 in B.unused, never called) is no store to A's
# field: no code may give A.value another value, so it reads as None. A store through another
# object (p.n = 3 in Q.fill) still types P.n.
class A:
    def __init__(self) -> None:
        self.value = None


class B:
    def __init__(self) -> None:
        self.value = 0

    def unused(self) -> None:
        self.value = 1


class P:
    def __init__(self) -> None:
        self.n = None


class Q:
    def __init__(self) -> None:
        self.n = 0

    def fill(self, p: P) -> None:
        self.n = 2
        p.n = 3


a = A()
print(a.value, a.value is None, B().value)
p = P()
print(p.n)
q = Q()
q.fill(p)
print(p.n, q.n)
