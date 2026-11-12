# error: a closure captures 'y' before the comprehension's for clause binds it
from typing import Callable


def table() -> None:
    saved: list[Callable[[], int]] = []
    [0 for x in [1] if saved.append(lambda: y) is None for y in [2]]


table()
