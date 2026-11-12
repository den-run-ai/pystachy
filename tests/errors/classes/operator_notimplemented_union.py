# error: NotImplemented may accompany one concrete native result type
from types import NotImplementedType


def result(value: int) -> int | str | NotImplementedType:
    if value == 1:
        return 1
    if value == 2:
        return "two"
    return NotImplemented


print(result(1) is NotImplemented)
