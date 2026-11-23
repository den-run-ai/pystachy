# A subclass of a subclass of a class template: a chain of classes without an __init__ of their
# own, and one with an __init__ that calls super().__init__(...) of a class whose own runs the
# template's, each overriding and calling super() methods (#962).
class Base:
    def __init__(self, value):
        self.value = value

    def name(self) -> str:
        return "base"

    def tell(self) -> str:
        return self.name() + "(" + str(self.value) + ")"


class Middle(Base):
    def name(self) -> str:
        return "middle<" + super().name() + ">"


class Leaf(Middle):
    def name(self) -> str:
        return "leaf<" + super().name() + ">"


class Fixed(Middle):
    def __init__(self) -> None:
        super().__init__(42)
        self.extra = "x"

    def name(self) -> str:
        return "fixed<" + super().name() + "," + self.extra + ">"


class Under(Fixed):
    def name(self) -> str:
        return "under<" + super().name() + ">"


xs = [Base(1), Middle(2), Leaf(3)]
for x in xs:
    print(x.tell())
ys = [Base("a"), Leaf("b")]
for y in ys:
    print(y.tell())
zs = [Base(0), Middle(5), Fixed(), Under()]
for z in zs:
    print(z.tell(), z.value + 1)
