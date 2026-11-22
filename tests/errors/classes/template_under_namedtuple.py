# error: inheritance from a NamedTuple is not supported
# A class template under a NamedTuple is not supported (#962), as no subclass of one is.
from typing import NamedTuple


class Pair(NamedTuple):
    a: int
    b: int


class Labeled(Pair):
    def __init__(self, label):
        self.label = label


print(Labeled("x").label)
