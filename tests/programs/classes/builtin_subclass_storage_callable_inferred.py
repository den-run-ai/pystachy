from typing import Callable


class Stack(list[int]):
    pass


class Box:
    def __init__(self, items):
        self.items = items


def make_box(items: list[list[int]]):
    return Box(items)


def apply(factory: Callable[[list[list[int]]], Box], items: list[list[int]]):
    return factory(items)


original = [[0]]
box = apply(make_box, original)


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        box.items.append(other)
        return isinstance(other, Stack)


print(Probe() == Stack([1]))
print(isinstance(original[1], Stack))
