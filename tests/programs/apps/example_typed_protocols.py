# A Protocol gives unrelated iterators one stored interface: the tutorial's checks, natively.
from typing import Iterable, Iterator, Protocol


class IntStream(Protocol):
    def __iter__(self) -> Iterator[int]: ...

    def __next__(self) -> int: ...


class Counter:
    def __init__(self, remaining: int) -> None:
        self.remaining = remaining

    def __iter__(self) -> "Counter":
        return self

    def __next__(self) -> int:
        if self.remaining == 0:
            raise StopIteration
        self.remaining -= 1
        return self.remaining


class Observed:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.value = 0

    def __iter__(self) -> "Observed":
        self.events.append("iter")
        return self

    def __next__(self) -> int:
        self.events.append("next")
        self.value += 1
        if self.value == 1:
            raise ValueError("source failed")
        if self.value == 2:
            return 17
        raise StopIteration


class Slot:
    def __init__(self, current: IntStream) -> None:
        self.current = current


class Source(Protocol):
    def __iter__(self) -> Iterator[int]: ...


class Words(Protocol):
    def __iter__(self) -> Iterator[str]: ...


def numbers() -> Iterator[int]:
    yield 9
    yield 10


def drain(stream: IntStream) -> list[int]:
    return list(stream)


def total(source: Source) -> int:
    result = 0
    for value in source:
        result += value
    return result


streams: list[IntStream] = [iter([1, 2]), iter((3, 4)), Counter(2), numbers()]
contents = [drain(stream) for stream in streams]
assert contents == [[1, 2], [3, 4], [1, 0], [9, 10]]
print("mixed", contents)

slot = Slot(iter([8]))
assert drain(slot.current) == [8]
slot.current = Counter(2)
assert drain(slot.current) == [1, 0]
print("field replacement ok")

source = iter([10, 20, 30, 40, 50])
assert next(source) == 10
left: IntStream = source
right: IntStream = source
assert left is right and left is source and iter(left) is source
assert [next(left), next(source), next(right), next(left)] == [20, 30, 40, 50]
assert next(right, -1) == -1 and next(left, -1) == -1
print("partial consumption and shared source ok")

events: list[str] = []
observed: IntStream = Observed(events)
assert events == []
caught = False
try:
    next(observed)
except ValueError as error:
    assert str(error) == "source failed"
    caught = True
assert caught and events == ["next"]
assert next(observed) == 17
assert next(observed, -1) == -1
assert events == ["next", "next", "next"]
print("lazy calls and exceptions", events)

values = [1]
live: IntStream = iter(values)
values.append(2)
assert next(live) == 1
values[1] = 3
assert next(live) == 3
assert next(live, -1) == -1
values.append(4)
assert next(live, -1) == -1
print("live mutation and exhaustion ok")

sources: list[Source] = [[1, 2], (3, 4), range(5, 7), {8: "x"}]
assert [total(s) for s in sources] == [3, 7, 11, 8]
assert [total(s) for s in sources] == [3, 7, 11, 8]
once: Source = numbers()
assert total(once) == 19 and total(once) == 0
print("repeatable iterables and one-shot generators ok")

texts: list[Words] = [["red", "blue"], ("green",)]
assert [" ".join(t) for t in texts] == ["red blue", "green"]
print("typed strings ok")
