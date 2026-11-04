from typing import Generic, TypeVar

T = TypeVar("T")


class Node(Generic[T]):
    def __init__(self, key: T) -> None:
        self.next: Node[T] | None = None
        self.key = key


n: Node[str] = Node("a")
n.next = Node("b")
print(n.key, n.next.key)
print(n.next.next is None)
values: list[Node[str]] = [n, Node("c")]
print([value.key for value in values])
