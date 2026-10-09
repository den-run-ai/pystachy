# error: a class attribute without an annotation (y = ...), which is no field of a dataclass, is not supported: annotate it
from dataclasses import dataclass


@dataclass
class D:
    x: int
    y = 2


print(D(1))
