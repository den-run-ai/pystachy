# A class deriving from typing's Iterator without __next__ leaves Iterator's abstract method:
# making one raises CPython's TypeError, and Iterator's own __iter__ returns the object
from typing import Iterator


class Half(Iterator[int]):
    def __iter__(self) -> "Half":
        return self


class Count(Iterator[int]):
    def __init__(self) -> None:
        self.n = 0

    def __next__(self) -> int:
        self.n += 1
        if self.n > 2:
            raise StopIteration
        return self.n


try:
    h = Half()
    print(h)
except TypeError as e:
    print("TypeError", e)
c = Count()
print(iter(c) is c, list(c))
