# pystachy: dynamic-any
# A generic callback may introduce a supported dynamic operation dispatcher.
from typing import Any


def add(left, right):
    return left + right


callback: Any = add
values: Any = [4, 5]
print(callback(*values))
values = ["left", "right"]
print(callback(*values))
