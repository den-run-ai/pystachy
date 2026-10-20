# error: type(x) is Box of an Any value is not supported: Box is a class template, whose objects are its specializations'
# pystachy: dynamic-any
# type(x) is C of an Any x compares exact types, which a class template's objects are not: each
# is of a specialization (rejected rather than answering False).
from typing import Any


class Box:
    def __init__(self, v):
        self.v = v


x: Any = Box(1)
print(type(x) is Box)
