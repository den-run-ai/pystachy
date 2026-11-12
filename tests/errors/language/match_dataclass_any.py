# error: class patterns require a concrete subject type; dynamic Any and union subjects are not supported
# pystachy: dynamic-any
from dataclasses import dataclass
from typing import Any


@dataclass
class Box:
    value: int


def classify(value: Any) -> int:
    match value:
        case Box(item):
            return item
        case _:
            return -1


print(classify(Box(7)))
