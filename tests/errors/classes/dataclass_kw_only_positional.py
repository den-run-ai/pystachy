# error: D.__init__() takes 1 positional argument but 2 were given
from dataclasses import dataclass


@dataclass(kw_only=True)
class D:
    a: int


print(D(1))
