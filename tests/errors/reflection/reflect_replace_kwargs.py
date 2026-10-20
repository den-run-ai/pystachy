# error: reflect_replace_kwargs.py:13: error: replace(obj, **changes) with a dict[str,int] is not supported: a key may name field name of Item (str), which a value of type int does not fit (#489)
from dataclasses import dataclass, replace


@dataclass
class Item:
    name: str
    qty: int


a = Item("pen", 2)
changes: dict[str, int] = {"qty": 7}
print(replace(a, **changes))
