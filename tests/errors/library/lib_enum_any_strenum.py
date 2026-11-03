# error: a Word member cannot become an Any value: a StrEnum member is an object of its class, where CPython's is also a str
# pystachy: dynamic-any
# An Any value of a StrEnum member would answer isinstance(v, str) as no str, where CPython's is one
from enum import StrEnum
from typing import Any


class Word(StrEnum):
    A = "a"


w: Any = Word.A
print(isinstance(w, str))
