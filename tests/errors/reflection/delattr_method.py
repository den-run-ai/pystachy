# error: delattr_method.py:6: error: the special method __delattr__ is not supported (CPython calls it to delete each attribute)
class Point:
    def __init__(self, x: int) -> None:
        self.x = x

    def __delattr__(self, name: str) -> None:
        print("kept", name)


print(Point(1).x)
