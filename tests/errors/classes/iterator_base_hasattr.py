# error: iterator_base_hasattr.py:19: error: hasattr() of '__orig_bases__' on an object of a class deriving from collections.abc's Iterator or Iterable is not supported
# CPython prints True: the subscripted base gives the class __orig_bases__
import collections.abc


class Once(collections.abc.Iterator[int]):
    def __init__(self) -> None:
        self.done = False

    def __iter__(self) -> "Once":
        return self

    def __next__(self) -> int:
        if self.done:
            raise StopIteration
        self.done = True
        return 1

print(hasattr(Once(), "__orig_bases__"))
