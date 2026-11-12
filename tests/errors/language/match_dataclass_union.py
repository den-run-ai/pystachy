# error: class patterns require a concrete subject type; dynamic Any and union subjects are not supported
from dataclasses import dataclass


@dataclass
class Box:
    value: int


@dataclass
class Other:
    value: int


def classify(value: Box | Other) -> int:
    match value:
        case Box(item):
            return item
        case _:
            return -1


print(classify(Box(7)))
