class Point:
    __slots__ = ("x",)
    count = 7

    def __init__(self) -> None:
        self.x = 1


p = Point()
print(Point.__slots__, p.__slots__, p.count)
print(Point.__slots__ is p.__slots__, p.__slots__ is p.__slots__)
Point.__slots__ = ("renamed",)
print(Point.__slots__, p.__slots__, Point().x)


class Empty:
    __slots__ = ()


class StringSlots:
    __slots__ = "value"

    def __init__(self, value):
        self.value = value


class ListSlots:
    __slots__: list[str] = ["item"]

    def __init__(self) -> None:
        self.item = 2


print(Empty.__slots__, Empty().__slots__)
print(StringSlots(3).__slots__, StringSlots("a").__slots__)
q = ListSlots()
ListSlots.__slots__.append("extra")
print(ListSlots.__slots__, q.__slots__, q.item)
print(ListSlots.__slots__ is q.__slots__, hasattr(q, "__slots__"))


class Base:
    __slots__ = ("a",)

    def __init__(self) -> None:
        self.a = 1


class Child(Base):
    __slots__ = ("b",)

    def __init__(self) -> None:
        super().__init__()
        self.b = 2


class Open(Base):
    pass


def show(base: Base) -> None:
    print(base.__slots__)


show(Base())
show(Child())
show(Open())
print(Child.__slots__, Open.__slots__)


class BaseError(Exception):
    __slots__ = ("message",)


class ChildError(BaseError):
    __slots__ = ("detail",)


class LeafError(ChildError):
    pass


# Concrete exception metadata and unmodified inherited metadata remain readable.
print(BaseError.__slots__, ChildError().__slots__, LeafError().__slots__)
print(ChildError.__slots__ is LeafError().__slots__)


class SharedError(Exception):
    __slots__ = ("value",)


class InheritedError(SharedError):
    pass


def shared(error: SharedError) -> None:
    print(error.__slots__)


shared(SharedError())
shared(InheritedError())
