# error: field 'y' is outside __slots__ of 'Child'
class Base:
    __slots__ = ("x",)

    def __init__(self) -> None:
        self.x = 1


class Child(Base):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__()
        self.y = 2


print(Child().x)
