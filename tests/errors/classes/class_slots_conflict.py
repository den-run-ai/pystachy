# error: 'x' in __slots__ conflicts with class variable or method
class Point:
    __slots__ = ("x",)
    x = 1


print(Point().x)
