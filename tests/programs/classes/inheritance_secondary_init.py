# A secondary base may have an __init__ that stores its attributes: they are fields of the classes
# that combine it, whose __init__ calls it as Sized.__init__(self, ...); where neither the class nor
# its primary chain defines __init__, the base's makes its objects, as CPython's method resolution
# order finds it; methods of the base read the attributes through a value of its type
class Base:
    def describe(self) -> str:
        return "base"


class Sized:
    def __init__(self, size: int = 1) -> None:
        self.size = size

    def grow(self, by: int) -> int:
        self.size += by
        return self.size


class Named:
    def __init__(self, name: str) -> None:
        self.name = name
        self.renamed = 0

    def rename(self, name: str) -> None:
        self.name = name
        self.renamed += 1


class Plain(Base, Sized):
    pass


class File(Base, Sized, Named):
    def __init__(self, name: str, size: int) -> None:
        Sized.__init__(self, size=size)
        Named.__init__(self, name)


def total(items: list[Sized]) -> int:
    return sum(s.grow(1) for s in items)


p = Plain(4)
q = Plain()
f = File("a", 3)
f.rename("b")
print(p.size, q.size, p.describe(), f.size, f.name, f.renamed, total([p, f, Sized(10)]), p.size, f.size)


class Tagged(Base, Named):
    def __init__(self, name: str) -> None:
        Named.__init__(self, name)
        self.tag: str = name.upper()


t = Tagged("x")
t.rename("y")
print(t.name, t.tag, t.renamed, isinstance(t, Named), isinstance(t, Sized))
