# What an object of a class template's specialization under an ordinary class (#962) has of that
# class's chain, as an object of an ordinary subclass does: the class attributes of every level,
# with their current values (a run-time Base.limit = 20 is seen, a mutable one is one object), as
# T, its member U and its subclass W bind them again; static methods, class methods through the
# template's name, properties, also through super(), and type(self).__name__.
class Root:
    a = "ra"
    shared: list[str] = []

    def __init__(self) -> None:
        self.n = 1

    def name(self) -> str:
        return type(self).__name__ + " " + self.a


class Mid(Root):
    b = "mb"


class Base(Mid):
    c = "bc"
    limit = 10

    def where(self) -> str:
        return self.a + "/" + self.b + "/" + self.c + " " + type(self).__name__

    @staticmethod
    def sm(x: int) -> int:
        return x * 2

    @classmethod
    def cm(cls) -> str:
        return "cm " + cls.c

    @property
    def twice(self) -> int:
        return self.limit * 2


class T(Base):
    c = "tc"

    def __init__(self, item):
        super().__init__()
        self.item = item

    def extra(self) -> str:
        return str(super().twice) + " " + str(super().sm(3))


class U(T):
    b = "ub"


class W(T):
    a = "wa"

    def __init__(self, item, more):
        super().__init__(item)
        self.more = more


rs: list[Root] = [Root(), Mid(), Base(), T(1), U(2), W(3, [4])]
for r in rs:
    print(r.name(), r.a, r.n)
xs: list[Base] = [Base(), T(1), T("s"), U(2), W(3, [4])]
for x in xs:
    print(x.where(), x.b, x.c)
t = T(5)
print(t.sm(2), t.twice, t.extra(), T.sm(4), T.cm(), T.limit, T.a, U.b, W.a)
t.limit = 5
print(t.limit, t.twice, Base.limit, T(6).limit)
Base.limit = 20
print(t.limit, T(7).limit, U(8).twice, W(9, 0).limit)
t.shared.append("t")
U(1).shared.append("u")
print(Root.shared, t.shared is Root.shared, len(W(0, 0).shared))
