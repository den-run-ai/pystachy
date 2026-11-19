# A __bytes__ annotated to return no bytes: CPython's TypeError where bytes() calls it, as the
# program runs; a program that never calls it compiles and runs as before.
import sys
from typing import Iterator


class B:
    def __bytes__(self) -> str:
        return "not bytes"

    def __iter__(self) -> Iterator[int]:
        return iter([65, 66])


if len(sys.argv) > 5:
    print(bytes(B()))
print("done")
if len(sys.argv) > 1:
    try:
        print(bytes(B()))
    except TypeError as e:
        print("TypeError", e)
