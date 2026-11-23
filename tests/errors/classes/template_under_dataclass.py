# error: inheritance from a dataclass is only supported by a @dataclass class
# A class template under a dataclass is not supported (#962): only one under an ordinary class,
# whose objects begin as a dataclass's do in no way of their own.
from dataclasses import dataclass


@dataclass
class Point:
    x: int
    y: int


class Tagged(Point):
    def __init__(self, tag):
        super().__init__(1, 2)
        self.tag = tag


print(Tagged("t").tag)
