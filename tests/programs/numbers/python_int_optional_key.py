# pystachy: python-int
# A missing optional key orders the promoting ints themselves; a present key is called.
from typing import Callable


def negative(value: int) -> int:
    return -value


def check(key: Callable[[int], int] | None) -> None:
    values = [2 ** 70, 1, -(2 ** 70)]
    print(min(values, key=key), max(values, key=key))
    print(min(2 ** 70, 1, -(2 ** 70), key=key))
    print(max(2 ** 70, 1, -(2 ** 70), key=key))
    print(min(3, 1, 2, key=key), max(3, 1, 2, key=key))
    print(sorted(values, key=key))
    values.sort(key=key)
    print(values)


check(negative)
check(None)
