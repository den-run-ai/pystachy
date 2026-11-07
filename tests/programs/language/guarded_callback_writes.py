# An entry guard must not freeze a callback parameter that the kernel can replace.
from collections.abc import Callable


def square(value: int) -> int:
    return value * value


def negative(value: int) -> int:
    return -value


def local_write(callback: Callable[[int], int], values: list[int]) -> list[int]:
    result: list[int] = []
    for value in values:
        result.append(callback(value))
        callback = negative
    return result


def cell_write(callback: Callable[[int], int], values: list[int]) -> list[int]:
    def replace() -> None:
        nonlocal callback
        callback = negative

    result: list[int] = []
    for value in values:
        result.append(callback(value))
        replace()
    return result


def argument_write(callback: Callable[[int], int], values: list[int]) -> list[int]:
    def argument(value: int) -> int:
        nonlocal callback
        callback = negative
        return value

    result: list[int] = []
    for value in values:
        result.append(callback(argument(value)))
    return result


callbacks: list[Callable[[int], int]] = [square, negative]
for callback in callbacks:
    print(local_write(callback, [2, 3, 4]))
    print(cell_write(callback, [2, 3, 4]))
    print(argument_write(callback, [2, 3, 4]))
