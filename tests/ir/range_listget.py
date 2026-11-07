import math


def tail(xs: list[float]) -> float:
    total = 0.0
    for i in range(1, len(xs)):
        total += abs(xs[i])
    return total if math.isfinite(total) else 0.0


def stride(xs: list[float]) -> float:
    total = 0.0
    for i in range(0, len(xs), 2):
        total += xs[i]
    return total


def captured(xs: list[float]) -> float:
    ys = xs
    n = len(ys)
    total = 0.0
    for i in range(1, n):
        j = i
        total += ys[j]
    return total


def entry_rebound(xs: list[float], ys: list[float]) -> float:
    xs = ys
    total = 0.0
    for i in range(1, len(xs)):
        total += xs[i]
    return total


def unknown_start(xs: list[float], start: int) -> float:
    total = 0.0
    for i in range(start, len(xs)):
        total += xs[i]
    return total


def changed_index(xs: list[float]) -> float:
    total = 0.0
    for i in range(1, len(xs)):
        i += 1
        total += xs[i]
    return total


def different_list(xs: list[float], ys: list[float]) -> float:
    total = 0.0
    for i in range(1, len(ys)):
        total += xs[i]
    return total
