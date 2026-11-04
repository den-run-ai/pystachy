# Preparing a template's fields must not execute or duplicate its class defaults.
from typing import Generic, TypeVar

T = TypeVar("T")
events: list[str] = []


def make_kind() -> str:
    events.append("kind")
    return "s"


class Stack(Generic[T]):
    kind = make_kind()
    seen: list[int] = []

    def __init__(self) -> None:
        self.items: list[T] = []


class Log:
    def __init__(self, rows: Stack[int]) -> None:
        self.rows = rows


print(events)
a: Stack[int] = Stack()
b: Stack[str] = Stack()
a.items.append(1)
b.items.append("x")
a.seen.append(9)
print(a.kind, b.kind, a.seen is b.seen, b.seen, Log(a).rows is a)
print(a.items, b.items, events)
