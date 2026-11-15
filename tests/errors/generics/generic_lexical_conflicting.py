# error: TypeVar 'T' is only supported in the annotations
from typing import TypeVar

T = TypeVar("T")


def choose(left: T, right: T):
    result: T = left
    return result


print(choose(1, "other"))
