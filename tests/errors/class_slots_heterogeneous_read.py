# error: reading __slots__ through Base is not supported when subclasses use different declaration types
class Base:
    __slots__ = ("x",)


class Child(Base):
    __slots__ = ["y"]


def show(base: Base) -> None:
    print(base.__slots__)


show(Child())
