# pystachy: dynamic-any
"""Union default arguments, which a dynamic program stores once as its definition runs: a call reads
them where the class or function is defined (a definition check, or code that runs only after)."""


class Span:
    def __init__(self, start: int | float = 0, scale: int | float = 1.5) -> None:
        self.total: float = start * 1.0 + scale

    def grown(self, by: int | float = 2) -> float:
        if isinstance(by, int):
            return self.total + by
        return self.total * by


def make() -> float:
    return Span(2).grown()


print(make(), Span().grown(0.5), Span(1, 2).total)
