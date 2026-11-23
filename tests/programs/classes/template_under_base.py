# Class templates under an ordinary class (#962): each specialization of T and of S derives from
# Base, so that a list of Base holds objects of all of them and of Base, and a call through a
# value of Base selects the object's override. show_all(), whose parameter is unannotated, is
# compiled for a list of Base at its first call, before the program makes its first T.
class Base:
    def __init__(self) -> None:
        self.filters: list[str] = []

    def hello(self) -> str:
        return "hi " + str(len(self.filters)) + " " + self.kind()

    def kind(self) -> str:
        return "base"

    def add(self, f: str) -> None:
        self.filters.append(f)


class T(Base):
    def __init__(self, name, level=0):
        super().__init__()
        self.name = name
        self.level = level

    def kind(self) -> str:
        return "t:" + str(self.name)


class U(T):
    def kind(self) -> str:
        return "u:" + super().kind()


class V(T):
    def __init__(self) -> None:
        super().__init__("v", 9)


class W(T):
    def __init__(self, name, extra):
        super().__init__(name)
        self.extra = extra


class S(Base):
    def __init__(self, size):
        super().__init__()
        self.size = size

    def kind(self) -> str:
        return "s" + str(self.size)


def show_all(xs):
    for x in xs:
        print(x.hello(), isinstance(x, T), isinstance(x, U), isinstance(x, Base), isinstance(x, S))


b = Base()
show_all([b])
t = T("a", 3)
t2 = T(7, "lvl")
u = U("u")
v = V()
w = W("w", [1, 2])
s = S(2.5)
xs: list[Base] = [b, t, t2, u, v, w, s]
for x in xs:
    x.add("f")
show_all(xs)
print(t.name, t.level, t2.name + 1, t2.level, u.level, v.name, v.level, w.extra, s.size)
t.filters.append("g")
xs[2].filters = ["h"]
print(len(t.filters), t.filters, t2.filters, b.filters, xs[1].filters is t.filters)
