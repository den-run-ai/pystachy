# __getattr__ (#1536) in a single-inheritance hierarchy: a class inherits its base's method or
# defines its own, which the object's class selects as for any method. A name that only a derived
# class defines is that class's attribute for its objects and the method's value for the others.
# A field that every object's __init__ assigns (also through super().__init__()) never reaches the
# method, whatever its type, also where only a derived class defines one.
class Base:
    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.asked: list[str] = []

    def __getattr__(self, name: str) -> int:
        self.asked.append(name)
        if name == "bad":
            raise AttributeError(f"{self.tag} has no {name}")
        return len(name)

    def width(self) -> int:
        return self.size + self.margin


class Wide(Base):
    def __init__(self, tag: str) -> None:
        super().__init__(tag)
        self.size = 100

    def grow(self) -> int:
        self.size += self.step
        return self.size


class Loud(Base):
    def __getattr__(self, name: str) -> int:
        self.asked.append(name.upper())
        return 1000 + len(name)


class Louder(Loud):
    margin = 1

    def __getattr__(self, name: str) -> int:
        return 2 * super().__getattr__(name)


class Quiet(Loud):
    pass


def show(b: Base) -> None:
    print(b.tag, b.color, b.width(), b.size, b.asked)
    print(getattr(b, "size"), getattr(b, "margin", -1), getattr(b, "bad", -2), hasattr(b, "size"), hasattr(b, "bad"))
    try:
        print(b.bad)
    except AttributeError as e:
        print("AttributeError:", e)


objs: list[Base] = [Base("b"), Wide("w"), Loud("l"), Louder("ll"), Quiet("q")]
for obj in objs:
    show(obj)
print([o.rank for o in objs], sum(o.size for o in objs))

w = Wide("w2")
print(w.size, w.other, w.grow(), w.grow(), w.asked)
ld = Louder("x")
print(ld.margin, ld.size, ld.asked, isinstance(ld, Base), ld.__getattr__("ab"))


class Wider(Wide):
    "inherits Wide.__init__, which calls Base.__init__ through super()"


wd = Wider("wd")
print(wd.tag, wd.asked, wd.size, wd.grow(), wd.asked, len(wd.tag))


class Shape:
    def __init__(self) -> None:
        self.sides = 4


class Blob(Shape):
    def __getattr__(self, name: str) -> str:
        return "blob " + name


def sides(s: Shape) -> int:
    return s.sides


print(sides(Shape()), sides(Blob()), Blob().corners, Blob().sides)
