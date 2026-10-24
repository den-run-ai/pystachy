# error: cannot compare list[Left] == list[Right]
# pystachy: dynamic-any
from typing import NamedTuple

class Left(NamedTuple):
    value: int

class Right(NamedTuple):
    value: int

left = [Left(1)]
right = [Right(1)]
print(left == right)
