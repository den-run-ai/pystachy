# A union of classes that may be None (A | B | None, whose None is a null box) compares None as
# CPython does: None == None, None != an object, and None < an object raises TypeError, also
# where a class defines __eq__ or __lt__ and where the value is a field.
class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def __lt__(self, other: object) -> bool:
        return isinstance(other, Base) and self.n < other.n


class A(Base):
    def __eq__(self, other: object) -> bool:
        return self is other


class B(Base):
    pass


def eq(x: A | B | None, y: Base | None) -> bool:
    return x == y


def ne(x: A | B | None, y: Base | None) -> bool:
    return x != y


def lt(x: A | B | None, y: Base) -> bool:
    return x < y


class Holder:
    def __init__(self) -> None:
        self.link: A | B | None = None

    def same(self, y: Base) -> bool:
        return self.link == y


b = B(1)
print(eq(None, None), ne(None, None), eq(None, b), ne(None, b), eq(b, b), eq(A(2), None))
try:
    print(lt(None, b))
except TypeError as e:
    print("TypeError", e)
print(lt(A(0), b), lt(b, A(0)))
h = Holder()
print(h.same(b))
h.link = b
print(h.same(b))
