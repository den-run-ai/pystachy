# error: iterator_base_dir.py:20: error: reflection of a Once object is not supported
# CPython's dir() lists __abstractmethods__, _abc_impl and __slots__, which ABCMeta and the
# abstract base give the class
from typing import Iterator


class Once(Iterator[int]):
    def __init__(self) -> None:
        self.done = False

    def __iter__(self) -> "Once":
        return self

    def __next__(self) -> int:
        if self.done:
            raise StopIteration
        self.done = True
        return 1

print([n for n in dir(Once()) if n.startswith("_abc")])
