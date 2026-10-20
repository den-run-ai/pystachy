# error: 'C' object has no attribute 'b'
# attrgetter("b") reads the attribute as o.b does, where it is compiled; CPython raises
# AttributeError where the getter runs
from operator import attrgetter


class C:
    def __init__(self) -> None:
        self.a = 1


print(attrgetter("b")(C()))
