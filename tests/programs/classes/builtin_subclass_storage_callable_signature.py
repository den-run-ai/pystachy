from typing import Callable


class Stack(list[int]):
    pass


def store(where: list[list[int]], value: Stack) -> None:
    where.append(value)


callback: Callable[[list[list[int]], Stack], None] = store
original = [[0]]
value = Stack([1])
callback(original, value)
print(isinstance(original[1], Stack))
print(original[1] is value)
