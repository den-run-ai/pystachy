# from weakref import * binds ref (weakref's __all__ here: tests/deviations/lib_weakref_all.py)
from weakref import *


class Item:
    def __init__(self, value: int):
        self.value = value


item = Item(1)
print(ref(item)() is item)
