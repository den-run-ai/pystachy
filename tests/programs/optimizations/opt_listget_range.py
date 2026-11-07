from typing import Callable, Iterator


def stepped(xs: list[float]) -> float:
    total = 0.0
    for i in range(1, len(xs), 9223372036854775807):
        total += xs[i]
    return total


def negative(xs: list[float]) -> float:
    total = 0.0
    for i in range(-1, len(xs)):
        total += xs[i]
    return total


def descending(xs: list[float]) -> float:
    total = 0.0
    for i in range(2, len(xs), -1):
        total += xs[i]
    return total


def shrink_before(xs: list[float]) -> float:
    total = 0.0
    try:
        for i in range(1, len(xs)):
            xs.pop()
            total += xs[i]
    except IndexError:
        return total
    return -100.0


def shrink_after(xs: list[float]) -> float:
    total = 0.0
    try:
        for i in range(1, len(xs)):
            total += xs[i]
            xs.pop()
    except IndexError:
        return total
    return -100.0


def alias_shrink(xs: list[float]) -> float:
    alias = xs
    total = 0.0
    try:
        for i in range(1, len(xs)):
            alias.pop()
            total += xs[i]
    except IndexError:
        return total
    return -100.0


def captured_shrink(xs: list[float]) -> float:
    n = len(xs)
    xs.pop()
    total = 0.0
    try:
        for i in range(1, n):
            total += xs[i]
    except IndexError:
        return total
    return -100.0


def rebound_loop(xs: list[float], ys: list[float]) -> float:
    total = 0.0
    try:
        for i in range(1, len(xs)):
            xs = ys
            total += xs[i]
    except IndexError:
        return total
    return -100.0


def rebound_capture(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    xs = ys
    total = 0.0
    try:
        for i in range(1, n):
            total += xs[i]
    except IndexError:
        return total
    return -100.0


def target_reassigned(xs: list[float]) -> float:
    total = 0.0
    try:
        for i in range(1, len(xs)):
            i += 1
            total += xs[i]
    except IndexError:
        return total
    return -100.0


def nested(xs: list[float]) -> float:
    total = 0.0
    for i in range(1, len(xs)):
        for j in range(1, len(xs)):
            total += xs[i] + xs[j]
    return total


def nested_target(xs: list[float]) -> float:
    total = 0.0
    try:
        for i in range(1, len(xs)):
            for i in range(5, 6):
                pass
            total += xs[i]
    except IndexError:
        return total
    return -100.0


def shorten(xs: list[float]) -> None:
    xs.pop()


def callback(xs: list[float], f: Callable[[list[float]], None]) -> float:
    total = 0.0
    try:
        for i in range(1, len(xs)):
            f(xs)
            total += xs[i]
    except IndexError:
        return total
    return -100.0


def suspended(xs: list[float]) -> Iterator[float]:
    for i in range(1, len(xs)):
        yield -1.0
        yield xs[i]


print("empty", stepped([]))
print("one", stepped([1.0]))
print("overflow step", stepped([1.0, 2.0, 3.0]))
print("negative", negative([1.0, 2.0, 3.0]))
print("descending empty", descending([1.0, 2.0, 3.0]))
print(shrink_before([1.0, 2.0, 3.0]))
print(shrink_after([1.0, 2.0, 3.0]))
print(alias_shrink([1.0, 2.0, 3.0]))
print(captured_shrink([1.0, 2.0, 3.0]))
print(target_reassigned([1.0, 2.0, 3.0]))
print(nested_target([1.0, 2.0, 3.0]))
print("rebind", rebound_loop([1.0, 2.0, 3.0], [4.0]))
print("captured rebind", rebound_capture([1.0, 2.0, 3.0], [4.0]))
print("nested", nested([1.0, 2.0, 3.0]))
print("callback", callback([1.0, 2.0, 3.0], shorten))
xs = [1.0, 2.0, 3.0]
g = suspended(xs)
print("suspend", next(g))
xs.clear()
try:
    print(next(g))
except IndexError:
    print("suspended index error")
