# pystachy: dynamic-any
# An object iterates through an Any value (#773): a for loop over one, and a pair of
# dict.update() that is one, call its __iter__, as CPython does (a documented deviation until
# then, which raised TypeError).
from typing import Any


class Pair:
    def __init__(self) -> None:
        self.items = ["k", "v"]

    def __iter__(self):
        return iter(self.items)


p: Any = Pair()
for x in p:
    print(x)
d: Any = {}
d.update([p])
print(d)
