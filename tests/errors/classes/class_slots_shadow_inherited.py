# error: shadowing inherited slot 'x' with a class variable or method is not supported
class Base:
    __slots__ = ("x",)


class Child(Base):
    __slots__ = ()
    x = 1


print(Child().x)
