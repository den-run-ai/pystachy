# error: getattribute_method.py:6: error: the special method __getattribute__ is not supported (CPython calls it to read each attribute)
class Point:
    def __init__(self, x: int) -> None:
        self.x = x

    def __getattribute__(self, name: str) -> int:
        return 42


print(Point(1).x)
