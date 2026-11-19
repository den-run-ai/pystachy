# After isinstance(x, (A, B)), x == y compares the object x is, also where the test narrows x to
# the union A | B because the code calls a method that A and B define and their base does not.
class Base:
    def __init__(self, n: int) -> None:
        self.n = n


class A(Base):
    def label(self) -> str:
        return "a" + str(self.n)


class B(Base):
    def label(self) -> str:
        return "b" + str(self.n)


def find(xs: list[Base], target: Base) -> int:
    for x in xs:
        if isinstance(x, (A, B)) and x == target:
            return x.n
    return -1


def name_of(xs: list[Base], target: Base) -> str:
    for x in xs:
        if isinstance(x, (A, B)) and x == target:
            return x.label()
    return "-"


b = B(7)
xs: list[Base] = [A(1), b, Base(9)]
print(find(xs, b), find(xs, B(7)), name_of(xs, b), name_of(xs, Base(9)))
