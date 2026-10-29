# pystachy: python-int
# Layouts shared by a closure, generator, recursive caller or module keep the full retry.
from typing import Iterator


def captured(count: int, step: int) -> int:
    total = 0

    def read() -> int:
        return total

    for i in range(count):
        total += step
    return read()


def generated(count: int, step: int) -> Iterator[int]:
    total = 0
    for i in range(count):
        total += step
        yield total


def recursive(count: int):
    if count == 0:
        return 0
    total = 0
    total += recursive(count - 1) + 2 ** 70
    return total


print(captured(3, 2 ** 70), captured(2, -(2 ** 63)))
print(list(generated(3, 2 ** 70)), list(generated(2, -(2 ** 63))))
print(recursive(3))
global_total = 0
for j in range(3):
    global_total += 2 ** 70
print(global_total)
