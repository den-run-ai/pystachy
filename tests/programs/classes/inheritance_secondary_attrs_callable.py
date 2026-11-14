# An attribute that a secondary base declares may hold a function, called through the base's type.
from typing import Callable


class Hooks:
    on_fail: Callable[[str], int]
    count: int

    def run(self, msg: str) -> int:
        self.count += self.on_fail(msg)
        return self.count


class Base:
    def __init__(self) -> None:
        self.tag = "b"


def size(msg: str) -> int:
    return len(msg)


class Tool(Base, Hooks):
    def __init__(self) -> None:
        super().__init__()
        self.on_fail = size
        self.count = 0


class Other(Base, Hooks):
    def __init__(self, k: int) -> None:
        super().__init__()
        self.extra = [k]
        self.count = 100
        self.on_fail = lambda msg: k


def fire(h: Hooks, msg: str) -> int:
    return h.on_fail(msg) + h.run(msg)


hs: list[Hooks] = [Tool(), Other(7)]
print([fire(h, "abc") for h in hs], [h.count for h in hs])
