# error: a tuple[Item, ...] as an Any value is not supported yet
# pystachy: dynamic-any
# A tuple of objects has no Any box yet: it is not stored where an Any value goes
from typing import Any


class Item:
    pass


items: tuple[Item, ...] = (Item(), Item())
value: Any = items
print(len(value))
