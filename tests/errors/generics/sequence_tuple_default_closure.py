# error: sequence_tuple_default_closure.py:6: error: expected list[int], got tuple[]
# CPython prints (): the nested function keeps the tuple default
from typing import Callable, Sequence


def keep(xs: Sequence[int] = ()) -> Callable[[], str]:
    def shown() -> str:
        return repr(xs)
    return shown


print(keep()())
