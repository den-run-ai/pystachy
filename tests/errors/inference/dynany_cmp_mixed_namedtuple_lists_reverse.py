# error: cannot compare list[Right] == list[Left]
# pystachy: dynamic-any
from typing import NamedTuple

class Left(NamedTuple):
    value: int

class Right(NamedTuple):
    value: int

left = [Left(1)]
right = [Right(1)]
print(right == left)
