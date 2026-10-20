# error: field 'y' is outside __slots__ of 'Point'
class Point:
    __slots__ = ("x",)

    def __init__(self) -> None:
        self.x = 1
        self.y = 2


print(Point().x)
