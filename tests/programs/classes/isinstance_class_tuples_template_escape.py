# isinstance(x, (A, B)) narrows x to A | B only where the union cannot type storage outside the
# function: a global that only None has held, given an object of a class template made from x
# (Box(x), whose field takes x's type), takes the specialization for x's declared Base
class Base:
    def __init__(self, n: int) -> None:
        self.n = n


class A(Base):
    pass


class B(Base):
    pass


class Box:
    def __init__(self, value):
        self.value = value


items = None


def add(x: Base) -> None:
    global items
    if isinstance(x, (A, B)):
        items = Box(x)


def show(b: Base) -> str:
    return type(b).__name__ + str(b.n)


add(A(1))
print(show(items.value) if items is not None else "-")
