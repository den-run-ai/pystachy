# pystachy: dynamic-any
# The supported singleton pattern rebinds the class name to an ordinary object.
# Construction through its captured type cannot reread that deleted binding.
from typing import Any


class Sentinel:
    marker: str = "kept"
Sentinel = Sentinel()

original: Any = Sentinel
factory: Any = type(original)
del Sentinel
first = factory()
print(type(first) is factory, first.marker, first is original)
try:
    print(Sentinel)
except NameError:
    print("name deleted")

Sentinel = original
second = factory()
print(type(second) is factory, second.marker, second is Sentinel, first is second)
