# error: callable_key_none.py:11: error: a key that may be None (Callable[[int | str], str] | None) is not supported for items of type int | str (the key of sorted()): test it with 'is not None' first
from typing import Callable


def text(x: int | str) -> str:
    return str(x)


k: Callable[[int | str], str] | None = text
xs: list[int | str] = [3, 1, 2]
print(sorted(xs, key=k))
