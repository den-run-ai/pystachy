# Classes the program never uses, whose class statements CPython fails to run when it imports
# this module.
from dataclasses import dataclass
from typing import Protocol


class Slotted:
    __slots__ = ("x",)
    x = 1


class Typed(Protocol[int]):
    pass


@dataclass
class Job:
    retries: int = 3
    run: list[int]

    def go(self, n):
        return n


class Plain:
    pass


class Sub(Plain[int]):
    pass


class Ratio:
    half = 1 // 0

    def get(self, n):
        return n


print("devmods.classes: loaded")
