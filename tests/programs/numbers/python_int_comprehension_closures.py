# pystachy: python-int
from typing import Callable


def readers(values: list[int]) -> list[Callable[[], int]]:
    return [lambda: value for value in values]


first = readers([2 ** 70, 2 ** 80])
second = readers([-2 ** 80, -2 ** 90])
print([f() for f in first], [f() for f in second])


def nested() -> None:
    values = [[lambda: value for value in [start, start + 1]] for start in [2 ** 70, 2 ** 80]]
    print([[f() for f in fs] for fs in values])


nested()
module_readers = [lambda: value for value in [2 ** 75, 2 ** 85]]
print([f() for f in module_readers])
