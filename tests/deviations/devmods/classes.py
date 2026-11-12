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

    def __init__(self, *n: int):  # (*args in __init__: a class Pystachy leaves uncompiled)
        self.n = n


class Ratio:
    n = int()  # (not a constant, which a later value of the body would read: class_body_consts.py)
    half = 1 // n
    whole = 1 // 0  # (after 1 // n, which Pystachy does not evaluate)

    def __init__(self, *n: int):  # (*args in __init__: a class Pystachy leaves uncompiled)
        self.n = n


class Later:
    half = 1 // 0

    def __init__(self, *n: int):  # (*args in __init__: a class Pystachy leaves uncompiled)
        self.n = n


print("devmods.classes: loaded")
