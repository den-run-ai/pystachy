# error: field '__slots__' is outside __slots__ of 'Point'
class Point:
    __slots__ = ("x",)

    def __init__(self) -> None:
        self.x = 1


p = Point()
p.__slots__ = ("other",)
