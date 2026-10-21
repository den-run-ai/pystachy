# error: reflect_vars_value.py:8: error: vars(x) and x.__dict__ are supported where they are printed
# A __dict__ kept as a value would have to be live: writes through it, reads after the object changes (#489)
class Point:
    def __init__(self, x: int) -> None:
        self.x = x


d = vars(Point(1))
print(d)
