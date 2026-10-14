# error: super() is only supported without arguments in a method of a class with a supported base
class Point:
    def __init__(self, x: int):
        super().__init__()
        self.x = x


print(Point(1).x)
