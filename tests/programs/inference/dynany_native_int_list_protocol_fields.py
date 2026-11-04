# pystachy: dynamic-any
# Comparison fallback guards must not decline native-list fields in iterator bodies.
from typing import Any


class Values:
    def __init__(self):
        self.items: list[int] = [1, 2]


class Reader:
    def __init__(self):
        self.source: Any = Values()
        self.values: list[int] = [3, 4]

    def __iter__(self):
        self.source.items = self.values
        return iter(self.source.items)


reader: Any = Reader()
print(list(reader))
