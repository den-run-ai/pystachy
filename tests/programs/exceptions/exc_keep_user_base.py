# A base exception class whose __init__ never calls BaseException.__init__ leaves the args its
# constructor was called with: str(e) and repr(e) of it and of its subclasses show all of them,
# also where a subclass's __init__ calls the base's with other values.
class Plain(Exception):
    def __init__(self, a: int, b: str) -> None:
        self.a = a
        self.b = b


class Sub(Plain):
    def __init__(self, a: int, b: str) -> None:
        self.c = a * 2
        super().__init__(a + 1, b + "!")


class Bare(Plain):
    pass


p = Plain(1, "x")
print(str(p), repr(p), p.a, p.b)
s = Sub(2, "y")
print(str(s), repr(s), s.a, s.b, s.c)
r = Bare(3, "z")
print(str(r), repr(r), r.a, r.b)
