# error: abc_iterator.py:5: error: unsupported type annotation
from collections.abc import Iterator


def first(it: Iterator[int]) -> int:
    return 0
