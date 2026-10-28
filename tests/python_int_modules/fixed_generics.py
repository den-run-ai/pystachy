# A module that does not opt in to promoting ints, whose generic class the program specializes for
# ints, which are promoting ints there too (tests/programs/numbers/python_int_generics.py).
from typing import Generic, TypeVar

T = TypeVar("T")


class Stack(Generic[T]):
    def __init__(self, first: T) -> None:
        self.top = first
        self.items: list[T] = [first]

    def push(self, v: T) -> None:
        self.top = v
        self.items.append(v)

    def pop(self) -> T:
        self.top = self.items[-2] if len(self.items) > 1 else self.top
        return self.items.pop()

    def peek(self) -> T:
        return self.top

    def total(self):
        # (unannotated: its arithmetic takes the promoting ints the stack holds)
        s = self.items[0] * 0
        for v in self.items:
            s += v
        return s


def made(n: int) -> Stack[int]:
    return Stack(n)


def pushed(s: Stack[int], n) -> None:
    # (n unannotated: the promoting int it is given, which an int parameter here would narrow)
    s.push(n)
