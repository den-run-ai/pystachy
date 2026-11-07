# Ordinary typed callback loops: runtime selection, distinct environments, and a binding
# changed by a later argument must all preserve the callback value already captured.
from collections.abc import Callable


def square(value: int) -> int:
    return value * value


def negative(value: int) -> int:
    return -value


def apply(callback: Callable[[int], int], values: list[int]) -> list[int]:
    result: list[int] = []
    for value in values:
        result.append(callback(value))
    return result


def shifted(amount: int) -> Callable[[int], int]:
    def callback(value: int) -> int:
        return value + amount
    return callback


class Shifted:
    def __init__(self, amount: int) -> None:
        self.amount = amount

    def apply(self, value: int) -> int:
        return value + self.amount


first = Shifted(4)
second = Shifted(9)
callbacks: list[Callable[[int], int]] = [
    square, negative, shifted(2), shifted(7), first.apply, second.apply,
]
for index in [0, 1, 2, 3, 4, 5, 0]:
    print(apply(callbacks[index], [1, 2, 3]))

selected: Callable[[int], int] = square
alias = selected


def inputs() -> list[int]:
    global selected
    selected = negative
    return [2, 3]


print(apply(selected, inputs()), apply(selected, [2, 3]), apply(alias, [2, 3]))

# A known top-level target can mutate the loop's input and raise after observable work.
seen: list[int] = []
pending: list[int] = [1, 2]


def observe(value: int) -> int:
    seen.append(value)
    if value == 1:
        pending[1] = 20
        pending.append(4)
    if value == 3:
        raise ValueError("callback")
    return value


print(apply(observe, pending), pending, seen)
pending = [1, 2, 3]
seen.clear()
try:
    print(apply(observe, pending))
except ValueError as error:
    print(str(error), pending, seen)
