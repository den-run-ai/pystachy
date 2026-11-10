# Empty displays use the items' type for tuples, iterators, generators and objects too.
from typing import Callable

values: list[list[int]] = [[1], [2]]
empty: list[list[int]] = []
pair: tuple[list[int], list[int]] = (values[0], values[1])
print(max(pair, default=[]), min(pair, default=[]))
print(max(iter(values), default=[]), min(iter(empty), default=[]))


def generate(items: list[list[int]]):
    for item in items:
        yield item


print(max(generate(values), default=[]), min(generate(empty), default=[]))
mapping = {"a": values[0], "b": values[1]}
print(max(mapping.values(), default=[]))
dicts: tuple[dict[str, int], dict[str, int]] = ({"a": 1}, {"b": 2, "c": 3})
print(max(dicts, default={}, key=len), min(iter(dicts), key=len, default={}))
events: list[str] = []


class Bag:
    def __init__(self, items: list[list[int]]) -> None:
        self.items = items

    def __iter__(self):
        events.append("iter")
        return iter(self.items)

    def __len__(self) -> int:
        raise ValueError("min and max must not request a length hint")


def make_key() -> Callable[[list[int]], int]:
    events.append("key")
    return len


print(max(Bag(values), default=[], key=make_key()) is values[0], events)
events.clear()
print(min(Bag(empty), key=make_key(), default=[]), events)
first = min(iter(empty), default=[])
second = min(generate(empty), default=[])
first.append(9)
print(first, second, first is second)
