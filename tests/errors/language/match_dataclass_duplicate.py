# error: Point() got multiple sub-patterns for attribute 'x'
from dataclasses import dataclass


@dataclass
class Point:
    x: int


match Point(1):
    case Point(value, x=other):
        print(value, other)
