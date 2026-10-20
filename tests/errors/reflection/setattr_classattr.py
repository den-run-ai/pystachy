# error: setattr_classattr.py:5: error: the special method __setattr__ is not supported (CPython calls it to assign each attribute)
# A class attribute binds a special method as a def does: CPython calls 0 where __init__ assigns
# self.x (TypeError: 'int' object is not callable).
class Point:
    __setattr__ = 0

    def __init__(self, x: int) -> None:
        self.x = x


try:
    print(Point(1).x)
except TypeError as e:
    print(e)
