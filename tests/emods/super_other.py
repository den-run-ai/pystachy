# super(A, self) in a method of B, a class deriving from A: CPython skips A's own __init__


class A(Exception):
    def __init__(self, m: str):
        super(A, self).__init__("A: " + m)


class B(A):
    def __init__(self, m: str):
        super(A, self).__init__(m)
