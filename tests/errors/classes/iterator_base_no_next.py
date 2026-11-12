# error: iterator_base_no_next.py:6: error: unsupported base class
# CPython raises TypeError: Can't instantiate abstract class Half without an implementation for abstract method '__next__'
from typing import Iterator


class Half(Iterator[int]):
    def __iter__(self) -> "Half":
        return self


try:
    print(Half())
except TypeError as e:
    print("TypeError")
