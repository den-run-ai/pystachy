# error: reading __slots__ through exception base Base is not supported when a subclass overrides it
class Base(Exception):
    __slots__ = ("a",)


class Child(Base):
    __slots__ = ("b",)


class Leaf(Child):
    pass


def show(error: Base) -> None:
    print(error.__slots__)


show(Leaf())
