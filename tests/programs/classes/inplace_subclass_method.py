# x op= y through a value typed with a class whose subclasses alone define the in-place method
# (#1538): CPython calls the in-place method of the object's own class, which changes the object,
# so other names for it see the change; an object of a class without one takes the binary
# operator, which rebinds x to a new object. Through a variable, a field, a list item, a dict
# value, a parameter, and the class that joins a display's or a conditional expression's classes.
import sys


class Base:
    def __init__(self, n: int):
        self.n = n

    def __add__(self, other: int) -> "Base":
        return Base(self.n + other)

    def __sub__(self, other: int) -> "Base":
        return Base(self.n - other)

    def __or__(self, other: int) -> "Base":
        return Base(self.n | other)


class Sub(Base):
    def __iadd__(self, other: int) -> "Sub":
        print("Sub.__iadd__", other)
        self.n += 100 * other
        return self

    def __isub__(self, other: int) -> "Base":
        self.n -= 100 * other
        return self


class Leaf(Sub):
    pass


class Other(Base):
    def __add__(self, other: int) -> "Base":
        print("Other.__add__", other)
        return Other(self.n + 1000 * other)


class Holder:
    def __init__(self, b: Base):
        self.b = b


def rhs(v: int) -> int:
    print("rhs", v)
    return v


def show(label: str, x: Base, y: Base) -> None:
    print(label, x.n, y.n, x is y)


def bump(v: Base) -> Base:
    v += 7
    return v


x: Base = Sub(1)
y = x
x += rhs(2)
show("variable", x, y)

h = Holder(Leaf(1))
y = h.b
h.b += 3
show("field", h.b, y)

items: list[Base] = [Base(1), Sub(1), Leaf(1), Other(1)]
olds = list(items)
for i in range(len(items)):
    items[i] += 4
    show("item", items[i], olds[i])

d: dict[str, Base] = {"a": Sub(5), "b": Base(5)}
y = d["a"]
d["a"] -= 1
show("dict", d["a"], y)
y = d["b"]
d["b"] -= 1
show("dict", d["b"], y)

x = Sub(6)
y = x
x |= 1
show("or", x, y)

k = len(sys.argv) - 1
z = Sub(1) if k == 0 else Other(5)
w = z
z += 2
show("conditional", z, w)

zs = [Sub(1), Other(5)]
olds = list(zs)
zs[0] += 2
zs[1] += 2
show("display", zs[0], olds[0])
show("display", zs[1], olds[1])

print([bump(o).n for o in [Base(1), Sub(1), Leaf(1), Other(1)]])
