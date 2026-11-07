# pystachy: python-int
# pystachy: dynamic-any
from typing import Any


events: list[str] = []


def item(label: str, n: int) -> int:
    events.append(label)
    return n


def small(n: int) -> tuple[int, ...]:
    return (item("small-first", n), item("small-second", -n))


def optional(n: int) -> tuple[int | None, ...]:
    return (item("optional", n), None, -n)


def dynamic(n: int) -> tuple[Any, ...]:
    return (item("huge-first", n), item("huge-second", n * n), None)


def converted(values: tuple[int, int]) -> tuple[Any, ...]:
    return values


print(small(2 ** 62 - 1), optional(2 ** 62 - 1))
big = 2 ** 80 + 123
kept = dynamic(big)
source = (big, -big)
print(kept, converted(source), source)
for i in range(100):
    garbage = dynamic(big + i)
print(kept, source, events[:5], len(events))
