# pystachy: dynamic-any
# a deque, a bytearray and a Counter held as Any values, compared with one another: each one's
# method returns NotImplemented for the others in CPython, so none is equal to another
from collections import Counter, deque
from typing import Any

values: list[Any] = [deque([1]), bytearray(b"a"), Counter("a"), deque([1]), bytearray(b"a"), Counter("a")]
for a in values:
    print(type(a).__name__, [a == b for b in values], [a != b for b in values], values.index(a), values.count(a))
