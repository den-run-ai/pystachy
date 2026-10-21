# Classes that Pystachy leaves uncompiled whose bodies run without raising
# (tests/programs/imports/deftime_class_raises.py). Skipped holds operations Pystachy does not evaluate, so it
# evaluates none in the classes after it: each calm_*.py module has one such operation first.
from typing import Iterable

NAMES = ["x"]
N = 0


class Computed:  # (operations that raise on other values)
    r: float = 1 / 3
    first: str = NAMES[0]
    n: int = int("5") // 2
    top = max(NAMES)
    data = {"a": 1, "b": "x", "c": int("3")}
    xs: Iterable[int]


class Skipped:  # (operations that CPython does not run)
    guarded = 1 // N if N else 0
    either = N and 1 // N
    if N:
        half = 1 // N
    xs: Iterable[int]


def after() -> str:
    return "calm: imported"
