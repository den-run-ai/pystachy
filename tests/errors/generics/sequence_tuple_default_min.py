# error: sequence_tuple_default_min.py:6: error: expected list[int], got tuple[]
# CPython raises TypeError: min() compares the tuple default with a list
from typing import Sequence


def shortest(xs: Sequence[int] = ()) -> int:
    for x in xs:
        print(x)
    return len(min(xs, [1]))


try:
    print(shortest())
except TypeError:
    print("TypeError")
