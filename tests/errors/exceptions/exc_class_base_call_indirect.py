# error: A.__init__(self, ...) in a method of C is supported only for its base, B (as super().__init__(...))
class A(Exception):
    def __init__(self, n: int):
        super().__init__(n)


class B(A):
    def __init__(self, n: int):
        super().__init__(n + 1)


class C(B):
    def __init__(self, n: int):
        A.__init__(self, n)


print(C(1))
