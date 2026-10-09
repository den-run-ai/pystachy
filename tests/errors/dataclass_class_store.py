# error: assigning to a class attribute of dataclass D (D.x = ...) is not supported
from dataclasses import dataclass


@dataclass
class D:
    x: int = 0


D.x = 5
print(D())
