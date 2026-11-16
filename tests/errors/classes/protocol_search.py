# error: protocol_search.py:16: error: comparing values of Named (in a list, tuple, in, count, index, sort, min or max) is not supported: their objects' classes are known only when the program runs (compare with 'is')
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class A:
    def name(self) -> str:
        return "a"


xs: list[Named] = [A()]
x = xs[0]
print(xs.index(x))
