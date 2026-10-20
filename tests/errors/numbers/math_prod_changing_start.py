# error: math.prod() must preserve its start type
from math import prod


class Changed:
    def __rmul__(self, value: str) -> int:
        return 42


print(prod([Changed()], start="a"))
