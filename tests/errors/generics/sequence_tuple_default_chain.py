# error: sequence_tuple_default_chain.py:6: error: expected list[int], got tuple[]
# CPython prints False: the chain also compares the tuple default with [] (0 not in xs and xs == [])
from typing import Sequence


def empty(xs: Sequence[int] = ()) -> bool:
    return 0 not in xs == []


print(empty())
