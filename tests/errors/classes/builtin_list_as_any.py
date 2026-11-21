# error: an object of Stack, a class that derives from list, as an Any value is not supported yet
# pystachy: dynamic-any
from typing import Any


class Stack(list[int]):
    pass


x: Any = Stack([1, 2])
print(x)
