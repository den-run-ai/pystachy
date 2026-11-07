from typing import Callable


def updated(xs: list[float]) -> float:
    total = 0.0
    for i in range(len(xs)):
        total += xs[i]
        xs[i] = total + 0.5
        total += xs[i]
    return total


def reversed_read(xs: list[float]) -> float:
    total = 0.0
    for i in range(len(xs)):
        xs.reverse()
        total += xs[i]
    return total


def copied_read(xs: list[float]) -> float:
    total = 0.0
    for i in range(len(xs)):
        copied = xs.copy()
        total += xs[i] + len(copied)
    return total


def sliced_read(xs: list[float]) -> float:
    total = 0.0
    for i in range(1, len(xs), 2):
        copied = xs[::2]
        total += xs[i] + len(copied)
    return total


def alias_updated(xs: list[float], ys: list[float]) -> float:
    total = 0.0
    for i in range(len(xs)):
        ys[0] = total
        total += xs[i]
    return total


def shrinking(xs: list[float]) -> float:
    total = 0.0
    for i in range(len(xs)):
        xs.reverse()
        xs.pop()
        total += xs[i]
    return total


def alias_shrinking(xs: list[float], ys: list[float]) -> float:
    total = 0.0
    for i in range(len(xs)):
        copied = xs.copy()
        ys.clear()
        total += xs[i] + len(copied)
    return total


def write_value(xs: list[float]) -> None:
    xs[0] = 10.0


def indirect_write(xs: list[float], callback: Callable[[list[float]], None]) -> float:
    total = 0.0
    for i in range(len(xs)):
        callback(xs)
        total += xs[i]
    return total


def direct_write(xs: list[float]) -> float:
    total = 0.0
    for i in range(len(xs)):
        write_value(xs)
        total += xs[i]
    return total


def changing_length(xs: list[float]) -> float:
    total = 0.0
    for i in range(len(xs)):
        xs.append(8.0)
        total += xs[i]
    return total


for size in [0, 1, 2, 7]:
    values = [float(i) + 0.25 for i in range(size)]
    work = values.copy()
    print(size, updated(work), work)
    print(reversed_read(values.copy()), copied_read(values), sliced_read(values))
    work = values.copy()
    print(alias_updated(work, work), work)
    print(indirect_write(values.copy(), write_value), direct_write(values.copy()))
    print(changing_length(values.copy()))

for mode in [0, 1]:
    values = [1.0, 2.0, 3.0]
    try:
        print(shrinking(values) if mode == 0 else alias_shrinking(values, values))
    except IndexError as error:
        print(type(error).__name__, str(error), values)
