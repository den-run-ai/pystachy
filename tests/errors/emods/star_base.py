"""What the star_rebound_*.py rejections take with import * or a from-import, then rebind."""


class Shape:
    def __init__(self, n: int) -> None:
        self.n = n


def greet(name: str) -> str:
    return "base " + name
