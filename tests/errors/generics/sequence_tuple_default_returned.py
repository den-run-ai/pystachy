# error: sequence_tuple_default_returned.py:6: error: expected list[int], got tuple[]
# CPython prints (): the function returns its tuple default, which an empty list would not be
from typing import Sequence


def first_or_all(xs: Sequence[int] = ()) -> Sequence[int]:
    return xs


print(first_or_all())
