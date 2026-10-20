# error: multiple __slots__ declarations are not supported; use one literal declaration
class Point:
    __slots__ = ("x",)
    __slots__ = ("y",)

    def __init__(self) -> None:
        self.x = 1


print(Point().x)
