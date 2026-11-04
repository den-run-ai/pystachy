from typing import Generic, TypeVar

T = TypeVar("T")


class Node(Generic[T]):
    def __init__(self, key: T) -> None:
        self.next: Node[T] | None = None
        self.key = key


class Holder(Generic[T]):
    def __init__(self, key: T) -> None:
        self.first: Node[T] = Node(key)


h = Holder("a")
h.first.next = Node("b")
print(h.first.key, h.first.next.key)
