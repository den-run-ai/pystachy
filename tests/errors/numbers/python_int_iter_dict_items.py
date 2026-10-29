# error: iter() of a dict's items() in __iter__ is not supported: its iterator raises if the dict changes size
# pystachy: python-int
# (items() of a dict of ints makes its tuples of promoting ints, bigints.big_items: the same view)
from typing import Iterator


class C:
    def __init__(self) -> None:
        self.d: dict[str, int] = {"a": 1, "b": 2}

    def __iter__(self) -> Iterator[tuple[str, int]]:
        return iter(self.d.items())  # (CPython's view sees the value changed below)


c = C()
for k, v in c:
    c.d["b"] = 99
    print(k, v)
