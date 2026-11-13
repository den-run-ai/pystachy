# error: sequence_tuple_default_len.py:10: error: expected list[int], got tuple[]
# CPython prints size: the function's own len is no builtin, so its call may see the tuple
from typing import Sequence


def size(s: Sequence[int]) -> str:
    return "size"


def f(xs: Sequence[int] = ()) -> str:
    len = size
    return len(xs)


print(f())
