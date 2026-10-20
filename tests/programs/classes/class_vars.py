# a class attribute assigned through its class (C.x = v, cls.x += 1) is the class's: C.x and the
# objects that have not assigned x themselves read its current value
class C:
    n: int = 0
    tag: str = "t"
    xs: list[int] = []

    def __init__(self) -> None:
        C.n += 1

    @classmethod
    def bump(cls) -> None:
        cls.n += 1

    @classmethod
    def retag(cls, s: str) -> None:
        cls.tag = s

    def show(self) -> str:
        return f"{self.n} {self.tag}"


a = C()
print(C.n, a.n, a.show())
C.bump()
b = C()
print(C.n, a.n, b.n, hasattr(a, "n"))
a.n = 100
print(C.n, a.n, b.n)
C.n = 7
print(C.n, a.n, b.n)
C.retag("u")
print(a.tag, b.tag, C.tag)
b.tag += "!"
print(a.tag, b.tag, C.tag)
C.xs += [1]
a.xs.append(2)
print(C.xs, a.xs, b.xs)
C.xs = [9]
print(C.xs, a.xs)


class D:
    k: int = 1

    def __init__(self, own: bool) -> None:
        if own:
            self.k = 50


def early() -> float:
    return E.v


class E:
    v: float = 1.5

    @staticmethod
    def set(x: float) -> None:
        E.v = x


d1 = D(True)
d2 = D(False)
D.k = 3
print(d1.k, d2.k, D.k)
print(early())
E.set(2.5)
print(early(), E().v)
