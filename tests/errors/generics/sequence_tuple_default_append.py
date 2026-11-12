# error: sequence_tuple_default_append.py:6: error: expected list[int], got tuple[]
# CPython raises AttributeError: a tuple has no append
from typing import Sequence


def grow(xs: Sequence[int] = ()) -> int:
    for x in xs:
        print(x)
    xs.append(1)  # type: ignore[attr-defined]
    return len(xs)


try:
    print(grow())
except AttributeError as e:
    print("AttributeError", e)
