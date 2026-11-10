# Empty defaults take their type from lazy inputs, as they do from direct lists.
from typing import Callable

values: list[list[int]] = [[1], [2]]
empty: list[list[int]] = []
print(max((x for x in values), default=[]), min((x for x in values), default=[]))
print(max((x for x in empty), default=[]), min((x for x in empty), default=[]))
print(max(map(lambda x: x, values), default=[]), min(map(lambda x: x, empty), default=[]))
print(max(reversed(values), default=[]), min(reversed(empty), default=[]))
print(max(filter(None, values), default=[]), min(filter(None, empty), default=[]))

first = max((x for x in empty), default=[])
second = max((x for x in empty), default=[])
first.append(9)
print(first, second, first is second)


def key_for(value: list[int]) -> Callable[[list[int]], int]:
    return len


def bound_by_keyword() -> None:
    # Typing the generator body must still follow a keyword's first binding.
    result = max((bound for _ in range(1)), default=[], key=key_for(bound := [7]))
    print(result, bound, result is bound)


bound_by_keyword()
events: list[str] = []


def source() -> list[list[int]]:
    events.append("source")
    return values


def item(value: list[int]) -> list[int]:
    events.append("item")
    return value


def make_key() -> Callable[[list[int]], int]:
    events.append("key")
    return len


print(max((item(x) for x in source()), default=[], key=make_key()), events)
events.clear()
print(min((item(x) for x in source()), key=make_key(), default=[]), events)
