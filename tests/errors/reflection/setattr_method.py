# error: setattr_method.py:6: error: the special method __setattr__ is not supported (CPython calls it to assign each attribute)
class Point:
    def __init__(self, x: int) -> None:
        self.x = x

    def __setattr__(self, name: str, v: int) -> None:
        print("set", name, v)


print(Point(1).x)
