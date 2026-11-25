from typing import Callable


class Stack(list[int]):
    pass


class Queue(list[int]):
    pass


stack = Stack([1])
queue = Queue([2])


def add_stack(where: list[list[int]]) -> None:
    where.append(stack)


def add_queue(where: list[list[int]]) -> None:
    where.append(queue)


def make_sink(value: Stack) -> Callable[[list[list[int]]], None]:
    def sink(where: list[list[int]]) -> None:
        where.append(value)
    return sink


closure = make_sink(stack)
callbacks: list[Callable[[list[list[int]]], None]] = [add_stack, add_queue, closure]
alias: list[Callable[[list[list[int]]], None]] = callbacks
original = [[0]]
view: list[list[int]] = original
for callback in alias:
    callback(view)
print(original is view, alias is callbacks)
print(isinstance(original[1], Stack), isinstance(original[2], Queue))
print(original[1] is stack, original[2] is queue, original[3] is stack)
original[1].append(5)
print(stack, original[3], queue)

optional: Callable[[list[list[int]]], None] | None = closure
if optional is not None:
    optional(original)
print(original[-1] is stack, original)
