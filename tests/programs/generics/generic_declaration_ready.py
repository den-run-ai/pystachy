# A method annotation specializes Stack before the global field-declaration pass.
from typing import Generic, TypeVar

T = TypeVar("T")


class Stack(Generic[T]):
    kind = "s"

    def __init__(self) -> None:
        self.items: list[T] = []


class Log:
    def __init__(self, rows: Stack[int]) -> None:
        self.rows = rows


s: Stack[int] = Stack()
s.items.append(7)
log = Log(s)
print(log.rows.kind, log.rows.items, log.rows is s)
