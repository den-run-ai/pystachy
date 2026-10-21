"""Type aliases, a TypeVar and a PEP 695 generic class for tests/programs/reflection/type_alias_imports.py."""
from typing import Callable, TypeVar

T = TypeVar("T")

Pos = int
Row = list[str]
Key = tuple[str, ...]
ParseFloat = Callable[[str], float]
Pair = tuple[T, T]
type Grid[V] = list[list[V]]
type Later = list[Node]
Unused = dict[str, list[int]]


class Node:
    def __init__(self, name: str) -> None:
        self.name = name


class Queue[E]:
    def __init__(self, first: E) -> None:
        self.items: list[E] = [first]

    def put(self, x: E) -> None:
        more: list[E] = [x]
        self.items.extend(more)

    def take(self) -> E:
        x: E = self.items[0]
        self.items = self.items[1:]
        return x


def width(r: Row) -> int:
    return len(r)


def origin() -> Pos:
    return 0
