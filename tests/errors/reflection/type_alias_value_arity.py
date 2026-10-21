# error: type_alias_value_arity.py:12: error: Too many arguments for <class '__main__.Box'>; actual 2, expected 1 (CPython evaluates this type alias's value when the assignment runs)
# (CPython raises the TypeError there, though no annotation names the alias)


class Box[T]:
    def __init__(self, x: T) -> None:
        self.x = x


Boxes = list[Box[int]]
print(Box(1).x)
Pairs = list[Box[int, str]]
print("never")
