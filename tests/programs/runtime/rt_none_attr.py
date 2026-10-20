from typing import Optional


class Cell:
    def __init__(self, v: int):
        self.v = v
        self.nxt: Optional[Cell] = None

    def bump(self) -> int:
        self.v += 1
        return self.v


def walk(c: Optional[Cell], steps: int) -> int:
    total = 0
    for _ in range(steps):
        total += c.bump()
        c = c.nxt
    return total


head = Cell(1)
head.nxt = Cell(10)
print(walk(head, 2))
print(walk(head, 3))
