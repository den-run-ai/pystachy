# pystachy: dynamic-any
# With dynamic Any, a module's sentinel annotated Final[Any] holds a dynamic value, for which a
# sentinel parameter's specialization cannot decide p is _dummy: the test runs at run time, and a
# store in its branch keeps the parameter's own type.
from typing import Any, Final

_dummy: Final[Any] = object()


class Node:
    def __init__(self, items: list[int], n: int) -> None:
        self.items = items
        self.n = n

    def copy_modified(self, items: list[int] = _dummy) -> "Node":
        return Node(items if items is not _dummy else self.items, self.n)

    def with_n(self, n: int = _dummy) -> "Node":
        if n is _dummy:
            n = self.n
        return Node(self.items, n + 1)


a = Node([1], 3)
print(a.copy_modified().items, a.copy_modified([2]).items, a.copy_modified(_dummy).items)
print(a.with_n().n, a.with_n(7).n, a.with_n(_dummy).n)
