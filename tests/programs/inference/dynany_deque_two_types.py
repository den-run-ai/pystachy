# pystachy: dynamic-any
# deques of two item types held as Any values, and never compared: the program compiles (the
# comparison helper of a deque of ints called another deque's _items(), which a deque of strs
# cannot answer with a boxed list)
from collections import deque
from typing import Any

held: list[Any] = [deque([1]), deque(["a"])]
print(len(held), len(held[0]), len(held[1]))
