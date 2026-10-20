# pystachy: dynamic-any
# An iterator class whose __iter__ is annotated -> Any, in a module that compiles typing.Any as
# dynamic values, iterates as in modules that do not opt in: iter() takes its own object (#782).
# Its __next__ -> Any gives Any items.
from typing import Any


class Count:
    def __init__(self, n: int) -> None:
        self.i = 0
        self.n = n

    def __iter__(self) -> Any:
        return self

    def __next__(self) -> Any:
        if self.i >= self.n:
            raise StopIteration
        self.i += 1
        return self.i


print(list(Count(3)), [x * 2 for x in Count(2)])
it = iter(Count(2))
print(next(it), next(it), next(it, 99))
print(2 in Count(3), 4 in Count(3))
