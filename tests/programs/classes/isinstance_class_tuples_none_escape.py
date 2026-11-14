# isinstance(x, (A, B)) narrows x to A | B only where the union cannot type storage outside the
# function: a global or field that only None has held so far takes x's declared Base, also as a
# list's items ([x]), as its readers expect
class Base:
    def __init__(self, n: int) -> None:
        self.n = n


class A(Base):
    pass


class B(Base):
    pass


class C(Base):
    pass


class Box:
    def __init__(self) -> None:
        self.held = None

    def keep(self, x: Base) -> None:
        if isinstance(x, (A, B)):
            self.held = [x]


items = None


def add(x: Base) -> None:
    global items
    if isinstance(x, (A, B)):
        items = [x]


def show(b: Base) -> str:
    return type(b).__name__ + str(b.n)


add(A(1))
box = Box()
box.keep(B(2))
print(show(items[0]) if items is not None else "-", show(box.held[0]) if box.held is not None else "-")
