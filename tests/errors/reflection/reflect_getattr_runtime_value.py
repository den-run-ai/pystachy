# error: reflect_getattr_runtime_value.py:9: error: getattr() of a name only the run time knows is supported where its text is used
# A run-time name's attribute as a value would need a type that holds any attribute's (#487, #489)
class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


v = getattr(Point(1, 2), input())
print(v)
