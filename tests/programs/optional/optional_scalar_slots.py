# Optional scalar locals must retain presence independently of their payload bits.
import math


def minimum(xs: list[int]) -> int:
    best: int | None = None
    for x in xs:
        if best is None or x < best:
            best = x
    return 17 if best is None else best


def rank_minimum(keys: list[int], ranks: dict[int, int]) -> int:
    best = None
    for key in keys:
        rank = ranks.get(key)
        if rank is not None and (best is None or rank < best):
            best = rank
    return -1 if best is None else best


def chosen(x: float, take: bool) -> float:
    value: float | None = x if take else None
    return 3.5 if value is None else value


def truth(x: bool, take: bool) -> int:
    value: bool | None = None
    if take:
        value = x
    if value is None:
        return -1
    return int(value)


def reset(xs: list[int]) -> int:
    value: int | None = None
    total = 0
    for x in xs:
        if x < 0:
            value = None
        else:
            value = x
        total += 23 if value is None else value
    return total


def caught(xs: list[int]) -> int:
    value: int | None = None
    for x in xs:
        try:
            if x == 0:
                raise ValueError("zero")
            value = x
        except ValueError:
            value = None
    return 9 if value is None else value


def escaped(x: int, take: bool) -> int | None:
    value: int | None = None
    if take:
        value = x
    return value


def copied(x: int, take: bool) -> int:
    value: int | None = None
    if take:
        value = x
    other: int | None = value
    return 19 if other is None else other


def keep(value: int | None) -> int:
    return 29 if value is None else value


def passed(x: int, take: bool) -> int:
    value: int | None = None
    if take:
        value = x
    return keep(value)


def stored(x: int, take: bool) -> list[int | None]:
    value: int | None = None
    if take:
        value = x
    return [value, value]


print([minimum([]), minimum([0]), minimum([7, 0, 4]), minimum([-3, -2, -4])])
queries: list[list[int]] = [[], [9], [1, 9, 2], [3, 1]]
print([rank_minimum(keys, {1: 3, 2: 0, 3: -4}) for keys in queries])
for number in [0.0, -0.0, float("nan"), float("inf"), -float("inf")]:
    result = chosen(number, True)
    print(result, math.copysign(1.0, result), math.isnan(result), chosen(number, False))
print([truth(x, take) for x in [False, True] for take in [False, True]])
print(reset([0, -1, 2, -3, 4]), caught([1, 0]), caught([0, 2]))
for take in [False, True]:
    print(escaped(0, take), copied(0, take), passed(0, take), stored(0, take))
