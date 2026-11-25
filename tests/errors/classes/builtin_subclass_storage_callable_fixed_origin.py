# error: expected list[Stack | list[int]], got list[list[int]]
from typing import Callable


class Stack(list[int]):
    pass


def store(where: list[list[int]], value: Stack) -> None:
    where.append(value)


def allocate() -> list[list[int]]:
    return [[0]]


callback: Callable[[list[list[int]], Stack], None] = store
callback(allocate(), Stack([1]))
