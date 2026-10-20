# Documented deviation (docs/dynamic-any.md): in a module that compiles typing.Any as dynamic
# values, an object is not iterable through an Any value yet (its __iter__ is not called), so a
# for loop over one, and a pair of dict.update() that is one, raise TypeError where CPython
# iterates the object (here it would print k, v and {'k': 'v'}).
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
