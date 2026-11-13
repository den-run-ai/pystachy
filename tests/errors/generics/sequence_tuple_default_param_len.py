# error: sequence_tuple_default_param_len.py:10: error: expected list[int], got tuple[]
# CPython prints tuple: the parameter len is the caller's function, which sees the default itself
from typing import Callable, Sequence


def kind(s: Sequence[int]) -> str:
    return type(s).__name__


def describe(len: Callable[[Sequence[int]], str], xs: Sequence[int] = ()) -> str:
    return len(xs)


print(describe(kind))
