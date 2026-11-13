# list() of an empty tuple default must scan a generic class's list of strs. Keep the
# live set small under GC stress; bounded short-lived strings also trigger ordinary GC.
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


box = fill(64)
junk = 0
for i in range(48):
    junk += len(str(i) * 1048576)
total = 0
for s in box.items:
    total += len(s)
print(total, box.items[0], box.items[63], junk)
numbers: Box[int] = Box()
numbers.push(5)
print(numbers.items, Box[float]((1.5,)).items)
