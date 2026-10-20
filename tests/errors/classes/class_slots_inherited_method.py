# error: slot 'value' shadows an inherited method or property: not supported
class Base:
    __slots__ = ()

    def value(self) -> int:
        return 7


class Child(Base):
    __slots__ = ("value",)


print(Child().value())
