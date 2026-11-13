# error: sequence_tuple_default_repr.py:6: error: expected list[int], got tuple[]
# CPython prints (): repr() tells a tuple from a list
from typing import Sequence


def show(xs: Sequence[int] = ()) -> None:
    print(len(xs), xs)


show()
