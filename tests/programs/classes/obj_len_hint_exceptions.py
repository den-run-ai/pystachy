# Catch only TypeError from the optional hint, and restore an outer exception.
from typing import Iterator


class UnknownLength(TypeError):
    pass


class Items:
    def __init__(self, mode: int) -> None:
        self.mode = mode

    def __iter__(self) -> Iterator[int]:
        print("iter", self.mode)
        if self.mode == 5:
            raise TypeError("iter failed")
        return iter([2, 1])

    def __len__(self) -> int:
        print("len", self.mode)
        if self.mode == 1:
            raise TypeError("unknown length")
        if self.mode == 2:
            raise UnknownLength("unknown subclass")
        if self.mode == 3:
            raise ValueError("length failed")
        if self.mode == 4:
            return -1
        return 2


for mode in range(6):
    for operation in range(3):
        try:
            if operation == 0:
                print("list", list(Items(mode)))
            elif operation == 1:
                print("sorted", sorted(Items(mode)))
            else:
                items = [0]
                items.extend(Items(mode))
                print("extend", items)
        except (TypeError, ValueError) as e:
            print(type(e).__name__, str(e))

for mode in range(1, 3):
    try:
        print(len(Items(mode)))
    except TypeError as e:
        print("direct", type(e).__name__, str(e))

try:
    raise ValueError("outer")
except ValueError:
    print(list(Items(2)))
    try:
        raise
    except ValueError as e:
        print("restored", str(e))


class BrokenIterator:
    def __iter__(self) -> "BrokenIterator":
        return self

    def __len__(self) -> int:
        raise TypeError("unknown length")

    def __next__(self) -> int:
        raise TypeError("next failed")


for operation in range(3):
    try:
        if operation == 0:
            print(list(BrokenIterator()))
        elif operation == 1:
            print(sorted(BrokenIterator()))
        else:
            more = [0]
            more.extend(BrokenIterator())
            print(more)
    except TypeError as e:
        print("iteration", str(e))
