# error: class patterns require a statically known dataclass
from dataclasses import dataclass


@dataclass
class Point:
    x: int


def choose(Point: int, value: int) -> int:
    match value:
        case Point():
            return 1
    return 0


print(choose(1, 2))
