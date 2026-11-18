"""Generators: a call returns at gen.start, before the body runs, and the caller runs while one is
suspended (test_lean_generators.py corrupts this program's IR)."""
from typing import Iterator

state: int | str = 0


def steps(n: int) -> Iterator[int]:
    # (a union local keeps its test across a suspension: no caller writes it)
    s: int | str = n if n > 0 else "none"
    if isinstance(s, int):
        yield s * 2
        yield s + 1


def bump() -> Iterator[int]:
    # (a union global may change while suspended: what it held before is tested again after)
    global state
    state = 5
    yield 0
    current = state
    if isinstance(current, int):
        yield current + 1


class Tally:
    total: int

    def __init__(self, start: int) -> None:
        self.count = start
        self.it = self.fill()  # (fill's body runs at the first next(), not here)
        self.label = f"tally {self.count}"

    def fill(self) -> Iterator[int]:
        self.total = self.count * 2
        yield self.total


t = Tally(3)
print(list(steps(2)), list(steps(0)), list(bump()), next(t.it), t.label, t.total)
b = bump()
print(next(b))
state = "s"
print(list(b), state)
