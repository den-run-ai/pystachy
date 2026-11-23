# class variables in a chain that holds a class template under ordinary classes, assigned
# through the base, through a class in between, through a class that derives from the template
# (U.y = v) and through a subclass whose own __init__ is a template (W.scale += v), and by the
# objects themselves: each object reads its own value, else its class's current one
# (template_under_class_variable.py: the classes that only bind the attribute again)
import enum


class Color(enum.Enum):
    RED = 1
    BLUE = 2


class Base:
    y = 1
    scale = 1.5
    favorite = Color.BLUE
    names: list[str] = ["base"]

    def both(self) -> str:
        return str(self.y) + "/" + str(self.scale) + "/" + self.favorite.name + "/" + ",".join(self.names)


class Mid(Base):
    y = 10


class T(Mid):
    scale = 2.5

    def __init__(self, item):
        self.item = item

    def own(self) -> str:
        return str(self.y) + ":" + str(self.scale)


class U(T):
    y = 3
    names: list[str] = ["u"]


class V(U):
    favorite = Color.RED


class W(T):
    scale = 4.5

    def __init__(self, item, more):
        super().__init__(item)
        self.more = more


class Plain(Base):
    def __init__(self, item):
        self.item = item


def show(xs: list[Base]) -> str:
    return " ".join([x.both() for x in xs])


def main() -> None:
    t = T(1)
    s = T("s")
    u = U(2)
    v = V(2.5)
    w = W(3, "m")
    p = Plain(b"p")
    m = Mid()
    xs: list[Base] = [t, s, u, v, w, p, m, Base()]
    print(show(xs))
    print(t.own(), s.own(), u.own(), v.own(), w.own(), p.y, U.y, T.scale, W.scale, V.favorite.name)
    Base.y = 7
    Mid.y = 70
    Base.scale = 0.5
    Base.favorite = Color.RED
    Base.names = ["new"]
    print(show(xs))
    print(t.own(), s.own(), u.own(), v.own(), w.own(), p.y, U.y, T.scale, W.scale, Mid.y)
    u.y = -1
    w.scale = -2.0
    t.names = ["mine"]
    U.y = 30
    W.scale += 1.0
    print(show(xs))
    print(t.own(), s.own(), u.own(), v.own(), w.own(), U(0).y, W(0, 0).scale, u.names == v.names)


main()
