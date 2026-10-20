# error: annotation_later_class.py:6: error: name 'Later' is not defined (CPython evaluates this annotation when the class body runs: quote it, or import annotations from __future__)
from typing import NamedTuple


class P(NamedTuple):
    b: Later


class Later(NamedTuple):
    v: int


print(P(Later(1)))
