# A class template whose base is an ordinary class, as logging's Logger derives from Filterer
# (#962): each specialization of T derives from Base, and U, without an __init__ of its own, has
# one specialization with each of T's.
class Base:
    def __init__(self) -> None:
        self.filters: list[str] = []

    def hello(self) -> str:
        return "hi " + str(len(self.filters))


class T(Base):
    def __init__(self, name, level=0):
        super().__init__()
        self.name = name
        self.level = level


class U(T):
    pass


t = T("a", 3)
u = U("b")
print(t.name, t.level, t.hello(), u.name, u.level, u.hello())
for x in [Base(), t, u]:
    print(x.hello(), isinstance(x, T), isinstance(x, U))
