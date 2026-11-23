# Subclasses of a class template that call its __init__ as Base.__init__(self, ...), as threading's
# _MainThread calls Thread.__init__(self, ...) (#962): the call decides which specialization of
# Base the class derives from as super().__init__(...) does, both for an annotated __init__
# (Fixed) and for one that is a class template too (Loose).
class Base:
    def __init__(self, name, level=0):
        self.name = name
        self.level = level

    def show(self):
        return f"{self.name}:{self.level}"


class Fixed(Base):
    def __init__(self, level: int) -> None:
        Base.__init__(self, "fixed", level)
        self.extra = level * 2

    def show(self):
        return "fixed " + Base.show(self)


class Loose(Base):
    def __init__(self, name, tag):
        Base.__init__(self, name, 7)
        self.tag = tag


f = Fixed(3)
lo = Loose("loose", "t")
for x in [Base("b", 1), f, lo]:
    print(x.show(), isinstance(x, Fixed), isinstance(x, Loose))
print(f.extra, lo.tag, lo.level)
