# x op= y where x is a union of objects and numbers: an object whose class defines the in-place
# method (__iadd__, __isub__) changes in place, so every name for it sees the change; a class
# without one makes a new object with __add__; a number computes as numbers do
class Acc:
    def __init__(self, n: int) -> None:
        self.n = n

    def __add__(self, other: int) -> "Acc":
        return Acc(self.n + other)

    def __sub__(self, other: int) -> "Acc":
        return Acc(self.n - other)

    def __iadd__(self, other: int) -> "Acc":
        self.n += 10 * other
        return self

    def __isub__(self, other: int) -> "Acc":
        self.n -= 100 * other
        return self

    def kind(self) -> str:
        return "Acc"


class Tip(Acc):
    def __iadd__(self, other: int) -> "Acc":
        self.n += 1000 * other
        return self

    def kind(self) -> str:
        return "Tip"


class Plain:
    def __init__(self, n: int) -> None:
        self.n = n

    def __add__(self, other: int) -> "Plain":
        return Plain(self.n + other)


def pick(f: int) -> "int | Acc":
    if f == 0:
        return 3
    if f == 1:
        return Acc(1)
    return Tip(1)


def show(v: "int | Acc") -> str:
    if isinstance(v, Acc):
        return v.kind() + " " + str(v.n)
    return "int " + str(v)


for f in range(3):
    x = pick(f)
    alias = x
    x += 2
    print(show(x), show(alias))
    x -= 1
    print(show(x), show(alias))


def plain(v: "int | Plain") -> str:
    if isinstance(v, Plain):
        return "Plain " + str(v.n)
    return "int " + str(v)


y: "int | Plain" = Plain(5)
before = y
y += 2
print(plain(y), plain(before))
