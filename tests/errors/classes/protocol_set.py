# error: protocol_set.py:16: error: set elements cannot be values of Named: an interface's objects hash and compare as their classes do, which only the run time knows
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class A:
    def name(self) -> str:
        return "a"


x: Named = A()
print(hash(x) == hash(x))
seen: set[Named] = set()
print(len(seen))
