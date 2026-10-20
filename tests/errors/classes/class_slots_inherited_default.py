# error: slot 'value' shadows an inherited class variable: not supported
class Base:
    __slots__ = ()
    value = 7


class Child(Base):
    __slots__ = ("value",)


print(Child().value)
