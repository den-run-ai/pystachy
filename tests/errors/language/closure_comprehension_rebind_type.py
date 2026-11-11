# error: comprehension variable 'x' is int in an earlier for clause and str in a later one
from typing import Callable


def table() -> None:
    saved: list[Callable[[], int]] = []
    [0 for x in [1] if saved.append(lambda: x) is None for x in ["changed"]]


table()
