# error: a class that derives from list with a decorator is not supported
from dataclasses import dataclass


@dataclass
class Stack(list[int]):
    depth: int = 0
