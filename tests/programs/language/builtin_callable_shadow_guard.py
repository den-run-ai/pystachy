# A callback named callable need not have the builtin's None-rejecting semantics.
from typing import Callable


class CallableObject:
    def __call__(self) -> int:
        return 1


def always(value: CallableObject | None) -> bool:
    return True


def check(value: CallableObject | None, callable: Callable[[CallableObject | None], bool]) -> None:
    if not callable(value):
        return
    if isinstance(value, CallableObject):
        print("object")
    else:
        print("none")


check(None, always)
check(CallableObject(), always)
