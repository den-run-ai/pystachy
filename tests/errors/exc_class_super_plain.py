# error: super() is only supported without arguments, in the methods of exception classes
class Point:
    def __init__(self, x: int):
        super().__init__()
        self.x = x


print(Point(1).x)
