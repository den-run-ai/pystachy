# error: non-default argument 'b' follows default argument 'a'
from dataclasses import dataclass


@dataclass
class C:
    a: int = 1
    b: int


print(C(2, 3))
