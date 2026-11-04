from typing import Generic, TypeVar

T = TypeVar("T")


class Node(Generic[T]):
    def __init__(self, key: T) -> None:
        self.next: "Node[T] | None" = None
        self.key = key


def make(key: str) -> Node[str]:
    return Node(key)


first = make("a")
first.next = make("b")
print(first.key, first.next.key)
