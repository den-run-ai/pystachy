# bytes(x) of a class with __bytes__ where x may be None: CPython's TypeError for None (a crash
# before), the object's __bytes__ otherwise, which CPython calls before it would iterate.
from typing import Iterator


class B:
    def __init__(self) -> None:
        self.data = b"xy"

    def __bytes__(self) -> bytes:
        return self.data

    def __iter__(self) -> Iterator[int]:
        return iter([65, 66])


def get(flag: bool) -> B | None:
    return B() if flag else None


for flag in (True, False):
    try:
        print(bytes(get(flag)))
    except TypeError as e:
        print("TypeError", e)
