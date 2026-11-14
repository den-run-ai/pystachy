"""Closed-union guards across calls, writes, joins and returns: union boxes are immutable."""


class Counter:
    def __init__(self) -> None:
        self.count = 0


total = 0


def bump(counter: Counter) -> None:
    global total
    counter.count += 1
    total += 1


def across_effects(value: int | str, counter: Counter) -> int:
    if isinstance(value, int):
        bump(counter)
        counter.count += 1
        return value * 2
    bump(counter)
    return len(value)


def joined(flag: bool, n: int, s: str) -> int:
    value: int | str = n if flag else s
    if isinstance(value, int):
        return value * 2
    return len(value)


def made(flag: bool) -> int | str:
    if flag:
        return 7
    return "seven"


def returned(flag: bool) -> int:
    value = made(flag)
    if isinstance(value, int):
        return value + 1
    return len(value)


def measured(value: float | str) -> float:
    if isinstance(value, str):
        return len(value) * 2.0
    return value * 2.0


counter = Counter()
print(across_effects(3, counter), across_effects("ab", counter), counter.count, total)
print(joined(True, 4, "x"), joined(False, 4, "xyz"), returned(True), returned(False), measured("ab"), measured(1.25))
