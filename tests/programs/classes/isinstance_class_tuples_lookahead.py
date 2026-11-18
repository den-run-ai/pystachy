# isinstance(x, (A, B)) narrows x to A | B only where the union cannot type storage outside the
# function: a global or field that only None has held, tested with `is None` before the store
# that gives it a value, takes x's declared Base too, as its readers expect
class Base:
    def __init__(self, n: int) -> None:
        self.n = n


class A(Base):
    pass


class B(Base):
    pass


class Box:
    def __init__(self) -> None:
        self.held = None

    def keep(self, x: Base) -> None:
        if isinstance(x, (A, B)):
            if self.held is None:
                self.held = [x]


items = None


def add(x: Base) -> None:
    global items
    if isinstance(x, (A, B)):
        if items is None:
            items = [x]


def show(b: Base) -> str:
    return type(b).__name__ + str(b.n)


add(B(2))
box = Box()
box.keep(A(1))
print(show(items[0]) if items is not None else "-", show(box.held[0]) if box.held is not None else "-")
