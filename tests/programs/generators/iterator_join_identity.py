# An Iterator[T] value is its iterator: advancing it advances the object, identity is shared,
# builtin iterators stay exhausted and a class iterator may resume.
from typing import Iterator


class Resumable:
    def __init__(self) -> None:
        self.items: list[int] = []

    def __iter__(self) -> "Resumable":
        return self

    def __next__(self) -> int:
        if len(self.items) == 0:
            raise StopIteration
        return self.items.pop(0)


def gen() -> Iterator[int]:
    yield 1
    yield 2
    yield 3


g = gen()
res = Resumable()
lst = [10, 20]
li = iter(lst)
held = [g, res, li]
print(held[0] is g, held[1] is res, held[2] is li, iter(held[0]) is held[0])
print(next(g), next(held[0]), next(g))
res.items.append(7)
print(list(held[1]))
res.items.append(8)
print(list(held[1]))
print(next(held[2]))
lst.append(30)
print(list(held[2]), list(held[2]))
lst.append(40)
print(list(li))
for it in held:
    print(next(it, -1))
