# error: copy.deepcopy() of a bound method is not supported: CPython binds its copy to a copy of its object
# CPython's copy is a method of a deep copy of c (printing 1)
import copy


class Cell:
    def __init__(self) -> None:
        self.v = 1

    def get(self) -> int:
        return self.v


c = Cell()
print(copy.deepcopy(c.get)())
