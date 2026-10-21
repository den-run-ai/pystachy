# error: new_method.py:9: error: the special method __new__ is not supported (CPython calls it to make each object of the class)
# CPython calls __new__ to make each object, before __init__: Pystachy, which makes objects
# itself, would leave out what it does.
class Point:
    def __init__(self, x: int) -> None:
        self.x = x
        print("init", x)

    def __new__(cls, x: int) -> None:
        print("new", x)


p = Point(1)
print(p)
