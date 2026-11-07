# The sole static target is eligible for a guarded version. Mutations, exceptions and
# closure misses must retain the ordinary loop's progress and callback side effects.
from collections.abc import Callable

seen: list[int] = []
values: list[int] = []


def observe(value: int) -> int:
    seen.append(value)
    if value == 1:
        values[1] = 20
        values.append(4)
    if value == 5:
        values.pop()
    if value == 3:
        raise ValueError("callback")
    return value * 2


def apply(callback: Callable[[int], int], items: list[int]) -> list[int]:
    result: list[int] = []
    for item in items:
        result.append(callback(item))
    return result


def shifted(amount: int) -> Callable[[int], int]:
    def callback(value: int) -> int:
        seen.append(value)
        return value + amount
    return callback


callbacks: list[Callable[[int], int]] = [observe, shifted(10), observe, shifted(20)]
for callback in callbacks:
    values = [1, 2]
    seen.clear()
    print(apply(callback, values), values, seen)
values = [5, 6, 7]
seen.clear()
print(apply(observe, values), values, seen)
values = [2, 3, 4]
seen.clear()
try:
    print(apply(observe, values))
except ValueError as error:
    print(str(error), values, seen)
