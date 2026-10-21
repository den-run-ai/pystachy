# error: slot 'value' shadows an inherited class variable: not supported
class Base:
    value: int = 7


class Middle(Base):
    __slots__ = ()


class Child(Middle):
    __slots__ = ("value",)


print(Child().value)
