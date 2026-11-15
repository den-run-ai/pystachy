# error: TypeVar 'T' is only supported in the annotations
from typing import TypeVar

T = TypeVar("T")
U = TypeVar("U")


def unrelated(value: U):
    result: T = value
    return result


def caller(value: T):
    result: T = value
    return unrelated(result)


print(caller(1))
