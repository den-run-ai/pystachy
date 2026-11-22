# A secondary base may extend a class whose __init__ stores attributes: the combining class's objects
# take that __init__ where neither the class nor its primary chain defines one, as CPython's method
# resolution order finds it, or call it through the base (Shared.__init__(self))
class Core:
    def __init__(self) -> None:
        self.name = "core"


class Shared(Core):
    def show(self) -> str:
        return "s"


class Base:
    pass


class C(Base, Shared):
    pass


class D(Base, Shared):
    def __init__(self) -> None:
        Shared.__init__(self)
        self.extra = 1


def names(xs: list[Shared]) -> list[str]:
    return [x.name + x.show() for x in xs]


c = C()
d = D()
c.name = "renamed"
print(c.name, c.show(), d.name, d.extra, isinstance(c, Core), names([c, d, Shared()]))
