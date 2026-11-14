# isinstance(x, (A, B)) narrows x to A | B only where the union cannot type storage that code
# outside the function reads: here the items of empty module globals that the guarded code fills
# (append, extend, a dict item, insert), which take x's declared Base, as their readers expect
class Base:
    def __init__(self, n: int) -> None:
        self.n = n


class A(Base):
    pass


class B(Base):
    pass


class C(Base):
    pass


items = []
later = []
reg = {}
seen = []


def add(x: Base) -> None:
    if isinstance(x, (A, B)):
        items.append(x)


def extend(x: Base) -> None:
    if isinstance(x, (A, B)):
        out = []
        out.append(x)
        later.extend(out)


def register(x: Base) -> None:
    if isinstance(x, (A, B)):
        reg[x.n] = x


def push(x: Base) -> None:
    if isinstance(x, (A, B)):
        seen.insert(0, x)


def show(b: Base) -> str:
    return type(b).__name__ + str(b.n)


def make(n: int) -> Base:
    if n == 0:
        return A(n)
    if n == 1:
        return C(n)
    return B(n)


for n in range(3):
    o = make(n)
    add(o)
    extend(o)
    register(o)
    push(o)
print(show(items[0]), show(items[1]), len(items))
print(show(later[1]), show(reg[2]), show(seen[0]), len(later), len(reg), len(seen))
