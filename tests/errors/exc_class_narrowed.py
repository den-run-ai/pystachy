# error: 'A' object has no attribute 'm' (it is a field of B, which derives from A: isinstance() does not change the type of a value)
class A(Exception):
    def __init__(self, n: int):
        super().__init__(n)
        self.n = n


class B(A):
    def __init__(self, n: int, m: int):
        super().__init__(n)
        self.m = m


def f(a: A) -> None:
    if isinstance(a, B):
        print("B", a.n, a.m)
    else:
        print("A", a.n)


f(A(1))
f(B(2, 3))
