from typing import Callable


class Stack(list[int]):
    pass


class Box:
    def __init__(self, items: list[list[int]]):
        self.items = items


def make_box(items: list[list[int]]) -> Box:
    return Box(items)


factory: Callable[[list[list[int]]], Box] = make_box
original = [[0]]
box = factory(original)


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        box.items.append(other)
        return len(other) == 1


value = Stack([1])
print(Probe() == value)
print(len(original[1]) == 1, original[1] == [1])
