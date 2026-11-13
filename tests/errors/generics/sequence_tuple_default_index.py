# error: sequence_tuple_default_index.py:6: error: expected list[int], got tuple[]
# CPython prints tuple index out of range: an empty list's IndexError would say list
from typing import Sequence


def first(xs: Sequence[int] = ()) -> int:
    for x in xs:
        print(x)
    return xs[0]


try:
    print(first())
except IndexError as e:
    print(e)
