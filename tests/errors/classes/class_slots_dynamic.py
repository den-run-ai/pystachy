# error: __slots__ needs a literal string, tuple or list of strings
names = ("x",)


class Point:
    __slots__ = names

    def __init__(self) -> None:
        self.x = 1


print(Point().x)
