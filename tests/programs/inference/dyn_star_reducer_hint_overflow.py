# pystachy: dynamic-any
# pystachy: python-int
# Wide length hints fail before consuming values, without truncating to native int.
from typing import Any


class Source:
    def __iter__(self) -> "Source":
        print("iter")
        return self

    def __next__(self) -> int:
        print("next must not run")
        raise StopIteration

    def __length_hint__(self) -> int:
        print("hint")
        return int("9223372036854775808")


def target() -> int:
    print("body must not run")
    return 7


function: Any = target
source: Any = Source()
try:
    print(function(*source))
except OverflowError as error:
    print(type(error).__name__, str(error))
