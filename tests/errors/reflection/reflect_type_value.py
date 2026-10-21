# error: reflect_type_value.py:8: error: type(x) as a value (a class object) is not supported (#7)
# A class object as a value is #7's; its name and identity tests are supported (#486)
class Point:
    def __init__(self, x: int) -> None:
        self.x = x


t = type(Point(1))
print(t)
