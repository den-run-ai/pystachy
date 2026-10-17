"""What mods.star_over and tests/star_rebound.py take with import * or a from-import, then rebind."""


class Error(Exception):
    pass


class Shape:
    def __init__(self, n: int) -> None:
        self.n = n

    def area(self) -> int:
        return self.n


def greet(name: str) -> str:
    return "base hello " + name


def helper() -> str:
    return "base helper"


LIMIT = 3
