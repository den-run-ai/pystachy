# pystachy: dynamic-any
# yield from uses the ordinary box/unbox contract for compatible channels.
from typing import Any, Iterator


class Item:
    def __init__(self, value: int) -> None:
        self.value = value


def integers() -> Iterator[int]:
    yield 1
    yield 2


def boxed_integers() -> Iterator[Any]:
    yield from integers()


def checked_integers() -> Iterator[int]:
    yield from boxed_integers()


print(list(boxed_integers()), list(checked_integers()))


def objects(item: Item) -> Iterator[Item]:
    yield item


def boxed_objects(item: Item) -> Iterator[Any]:
    yield from objects(item)


item = Item(7)
boxed = next(boxed_objects(item))
print(boxed is item, boxed.value)
boxed.value = 8
print(item.value)


def values(value: Any) -> Iterator[Any]:
    yield value


def checked_objects(value: Any) -> Iterator[Item]:
    yield from values(value)


def checked_lists(value: Any) -> Iterator[list[Any]]:
    yield from values(value)


print(next(checked_objects(item)) is item)
shared: list[Any] = [1]
received = next(checked_lists(shared))
received.append("same list")
print(received is shared, shared)
