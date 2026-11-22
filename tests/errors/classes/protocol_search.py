# error: protocol_search.py:16: error: comparing values of Named (in a list, tuple, in, count, index, sort, min or max) is not supported: the runtime's searches and sorts do not reach their objects' methods (compare them with == or 'is' in a loop)
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class A:
    def name(self) -> str:
        return "a"


xs: list[Named] = [A()]
x = xs[0]
print(xs.index(x))
