# Properties with setters and deleters in a single-inheritance hierarchy: a subclass's
# @property def starts a new property (without the base's setter and deleter), while
# @Base.x.setter keeps the base's getter and deleter; a base-typed receiver calls the methods
# of its object's class.


class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    @property
    def n(self) -> int:
        return self._n

    @n.setter
    def n(self, v: int) -> None:
        print("Base.set", v)
        self._n = v

    @n.deleter
    def n(self) -> None:
        print("Base.del")
        self._n = -1

    def describe(self) -> str:
        return f"n={self.n}"


class ReadOnly(Base):
    @property
    def n(self) -> int:
        return self._n * 10


class Logged(Base):
    @Base.n.setter
    def n(self, v: int) -> None:
        print("Logged.set", v)
        self._n = v + 100


class Plain(Base):
    pass


class Own(Plain):
    @property
    def n(self) -> int:
        return super().n + 1000

    @n.setter
    def n(self, v: int) -> None:
        print("Own.set", v)
        self._n = v * 2


def assign(b: Base, v: int) -> None:
    try:
        b.n = v
        print("now", b.n, b.describe())
    except AttributeError as e:
        print("error", e)


def remove(b: Base) -> None:
    try:
        del b.n
        print("removed", b.n)
    except AttributeError as e:
        print("error", e)


for x in [Base(1), Plain(2), Logged(3), Own(4)]:
    assign(x, 5)
    remove(x)
    x.n += 1
    print(x.describe())

try:
    ReadOnly(6)
except AttributeError as e:
    print("constructor", e)

r: Base = Logged(7)
r.n = 8
print(r.n)
p = Plain(9)
p.n -= 4
print(p.n)
o = Own(10)
o.n = 11
print(o.n)
del o.n
print(o.n)
