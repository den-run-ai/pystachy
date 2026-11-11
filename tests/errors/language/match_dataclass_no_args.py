# error: Point() accepts 0 positional sub-patterns (1 given)
from dataclasses import dataclass


@dataclass(match_args=False)
class Point:
    x: int


match Point(1):
    case Point(x):
        print(x)
