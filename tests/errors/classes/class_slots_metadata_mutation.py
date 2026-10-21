# error: field 'extra' is outside __slots__ of 'Point'
class Point:
    __slots__ = ["x"]

    def __init__(self) -> None:
        self.x = 1


Point.__slots__.append("extra")
p = Point()
p.extra = 2
