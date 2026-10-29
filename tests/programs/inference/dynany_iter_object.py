# pystachy: dynamic-any
from typing import Any


class Pair:
    def __init__(self) -> None:
        self.items = ["k", "v"]

    def __iter__(self):
        return iter(self.items)


p: Any = Pair()
try:
    for x in p:
        print(x)
except TypeError as e:
    print("TypeError:", e)
d: Any = {}
try:
    d.update([p])
    print(d)
except TypeError as e:
    print("TypeError:", e)
