# The methods of an exception class may call their base's as Base.method(self, ...), as older
# code does, and as super(C, self).method(...): both are super().method(...).
class E(Exception):
    def __init__(self, m: str):
        Exception.__init__(self, m)
        self.m = m


class A(Exception):
    def __init__(self, n: int):
        super().__init__(n)
        self.n = n

    def __str__(self) -> str:
        return "A!" + str(self.n)


class B(A):
    def __init__(self, n: int, m: int):
        A.__init__(self, n)
        self.m = m

    def __str__(self) -> str:
        return "B:" + A.__str__(self)

    def __repr__(self) -> str:
        return "B/" + A.__repr__(self)


class C(Exception):
    def __init__(self, m: str):
        super(C, self).__init__(m)


b = B(1, 2)
print(b, repr(b), b.n, b.m)
print(E("x").m, repr(E("y")), C("z"), repr(C("w")))
raise E("hi")
