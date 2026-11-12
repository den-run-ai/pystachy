# error: class patterns require a concrete subject type; dynamic Any and union subjects are not supported
# pystachy: dynamic-any
from dataclasses import dataclass
from typing import Any


@dataclass
class Box:
    value: int


@dataclass
class Outer:
    value: Any


def classify(value: Outer) -> int:
    match value:
        case Outer(Box(item)):
            return item
        case _:
            return -1


print(classify(Outer(Box(7))))
