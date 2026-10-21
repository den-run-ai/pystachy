# pystachy: dynamic-any
# Independent reproducer of #816's reported global-inference contamination.
# The first speculative comparison refines xs before it is declined. A clean
# pass must still compile B.__eq__ for an Any holding a string. CPython: True.
from typing import Any

xs = []


class A:
    def __init__(self):
        self.items = [1]

    def __eq__(self, other):
        if isinstance(other, int):
            xs.append(1)
        return self.items == other.items


class B:
    def __eq__(self, other):
        if isinstance(other, str):
            xs.append("s")
            return True
        return False


a: Any = A()
b: Any = B()
s: Any = "x"
print(b == s)
