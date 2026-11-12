# list() of an empty tuple default, kept in a generic class's list of strs: its array must be one
# the collector scans, or the strs it holds are freed while in use.
from typing import Generic, Iterable, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, items: Iterable[T] = ()) -> None:
        self.items: list[T] = list(items)

    def push(self, x: T) -> None:
        self.items.append(x)


def fill(n: int) -> Box[str]:
    box: Box[str] = Box()
    for i in range(n):
        box.push("s" + str(i) * 3)
    return box


box = fill(2000)
junk = []
for i in range(300000):
    junk.append(str(i) * 20)
total = 0
for s in box.items:
    total += len(s)
print(total, box.items[0], box.items[1999], len(junk))
numbers: Box[int] = Box()
numbers.push(5)
print(numbers.items, Box[float]((1.5,)).items)
