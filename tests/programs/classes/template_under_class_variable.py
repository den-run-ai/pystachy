# a class variable of an ordinary class (Base.y = v somewhere in the program) that a class under
# it binds again in its class body, where that class is a class template, a class that derives
# from one, or a subclass whose own __init__ is a template: its objects read their own class's
# value through their own type, through the base's methods and through a location of the base's
# type, before and after the base's is assigned. Each shape has its own classes, and the program
# has no `is` and assigns nothing through the classes that bind the attribute again: either
# stores the value in the class's global by another path
import enum


class Color(enum.Enum):
    RED = 1
    BLUE = 2


class A:
    y = 1

    def both(self) -> str:
        return "y" + str(self.y)


class AT(A):
    def __init__(self, item):
        self.item = item

    def own(self) -> int:
        return self.y


class AU(AT):
    y = 3


class B:
    y = 1


class BT(B):
    y = 2

    def __init__(self, item):
        self.item = item


class C:
    y = 1


class CT(C):
    def __init__(self, item):
        self.item = item


class CU(CT):
    y = 3

    def __init__(self, item):
        super().__init__(item)
        self.more = item


class D:
    x = "base"

    def read(self) -> str:
        return self.x + "/" + type(self).__name__


class DMid(D):
    y = 1

    def both(self) -> str:
        return self.x + str(self.y)


class DT(DMid):
    def __init__(self, item):
        self.item = item

    def show(self) -> str:
        return self.read() + "|" + self.both() + "|" + str(self.item)


class DU(DT):
    y = 3


class E:
    favorite = Color.BLUE
    scale = 1.5
    label: str | None = None

    def describe(self) -> str:
        return self.favorite.name + " " + str(self.scale) + " " + str(self.label)


class ET(E):
    def __init__(self, item, other=None):
        self.item = item
        self.other = other


class EW(ET):
    scale = 2.5

    def __init__(self, item):
        super().__init__(item, "w")
        self.extra = [item]


def shape_a() -> None:
    u = AU(2)
    t = AT(1)
    xs: list[A] = [u, t, AU("s")]
    print(u.y, u.own(), u.both(), AU.y, t.y, t.own(), t.both(), AT.y, [x.both() for x in xs])
    A.y = 7
    print(u.y, u.own(), u.both(), AU.y, t.y, t.own(), t.both(), AT.y, [x.both() for x in xs])


def shape_b() -> None:
    t = BT(1)
    s = BT("s")
    print(t.y, s.y, BT.y, B.y)
    B.y = 7
    print(t.y, s.y, BT.y, B.y, B().y)


def shape_c() -> None:
    u = CU(2)
    v = CU("s")
    print(u.y, v.y, CU.y)
    C.y = 7
    print(u.y, v.y, CU.y, C.y, CT(0).y)


def shape_d() -> None:
    t = DT(1.5)
    s = DT("s")
    u = DU(2)
    m = DMid()
    print(t.show(), s.show(), u.show(), m.read(), m.both())
    DMid.y = 7
    D.x = "new"
    print(t.show(), s.show(), u.show(), m.read(), m.both())
    xs: list[D] = [t, s, u, m]
    print([x.read() for x in xs])


def shape_e() -> None:
    t = ET(1)
    u = ET("s", 2.0)
    w = EW(3)
    print(t.describe(), "|", u.describe(), "|", w.describe())
    E.favorite = Color.RED
    E.label = "L"
    E.scale = 0.5
    print(t.describe(), "|", u.describe(), "|", w.describe())
    u.label = None
    u.scale = 9.0
    print(t.describe(), "|", u.describe(), "|", w.describe(), isinstance(w, ET), isinstance(w, E))


shape_a()
shape_b()
shape_c()
shape_d()
shape_e()
