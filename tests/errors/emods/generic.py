from typing import TypeVar

_D = TypeVar("_D")


def default(d: _D) -> _D:
    return d


class Box:
    def __init__(self, v: int) -> None:
        self.v = v

    def get(self, default: _D) -> int:
        return self.v
