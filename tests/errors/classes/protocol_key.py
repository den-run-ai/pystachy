# error: protocol_key.py:14: error: dict keys cannot be values of Named: an interface's objects hash and compare as their classes do, which only the run time knows
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class A:
    def name(self) -> str:
        return "a"


seen: dict[Named, int] = {}
print(len(seen))
