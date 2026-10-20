# error: __slots__ entry '__x' is not supported
class Point:
    __slots__ = ("__x",)


print(Point())
