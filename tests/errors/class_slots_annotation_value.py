# error: expected int, got str
class Point:
    __slots__: list[int] = ["x"]

    def __init__(self) -> None:
        self.x = 1


print(Point().x)
