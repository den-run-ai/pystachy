# int() and float() of an object ask its own class: a derived class that defines __int__ or
# __float__ where its base has __index__, or no method at all, is converted by its own
# method through a base-typed reference, and a class that has none raises TypeError.
class Base:
    def __index__(self) -> int:
        return 3


class Child(Base):
    def __int__(self) -> int:
        return 9

    def __float__(self) -> float:
        return 9.5


class Grand(Child):
    def __int__(self) -> int:
        return 27


class Other(Base):
    def __index__(self) -> int:
        return 4


class Plain:
    def __init__(self, n: int) -> None:
        self.n = n


class Counted(Plain):
    def __int__(self) -> int:
        return self.n


class Ratio(Plain):
    def __float__(self) -> float:
        return self.n / 2


def show(x: Base) -> None:
    print(int(x), float(x))


def whole(x: Plain) -> None:
    try:
        print(int(x))
    except TypeError as e:
        print("TypeError:", e)


def real(x: Plain) -> None:
    try:
        print(float(x))
    except TypeError as e:
        print("TypeError:", e)


def pick(n: int) -> Base:
    return [Base(), Child(), Grand(), Other()][n]


for i in range(4):
    show(pick(i))
for p in [Plain(1), Counted(5), Ratio(7)]:
    whole(p)
    real(p)
none: Base = pick(0) if len("x") > 1 else None
try:
    print(int(none))
except TypeError as e:
    print("TypeError:", e)
try:
    print(float(none))
except TypeError as e:
    print("TypeError:", e)
