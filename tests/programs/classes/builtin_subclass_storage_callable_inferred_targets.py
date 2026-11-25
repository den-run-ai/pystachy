from typing import Callable


class Stack(list[int]):
    pass


class Queue(list[int]):
    pass


class Box:
    def __init__(self, value):
        self.value = value


stack = Stack([1])
queue = Queue([2])


def make_stack(items: list[list[int]]):
    items.append(stack)
    return Box(10)


def make_queue(items: list[list[int]]):
    items.append(queue)
    return Box(20)


def apply(factory: Callable[[list[list[int]]], Box], items: list[list[int]]):
    return factory(items)


original = [[0]]
first = apply(make_stack, original)
second = apply(make_queue, original)
print(first.value, second.value)
print(isinstance(original[1], Stack), isinstance(original[2], Queue))
print(original[1] is stack, original[2] is queue)
original[1].append(5)
print(stack, queue, original)
