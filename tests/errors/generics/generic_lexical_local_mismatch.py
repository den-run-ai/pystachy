# error: expected int, got str
from typing import TypeVar

T = TypeVar("T")


def wrong(value: T) -> T:
    result: T = "wrong"
    return result


print(wrong(1))
