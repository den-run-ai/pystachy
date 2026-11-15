# An explicit callable field gives unrelated iterators one stored interface.
from adapter import TypedIterator, int_iterator


class Counter:
    def __init__(self, remaining: int) -> None:
        self.remaining = remaining

    def __iter__(self):
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

    def __iter__(self):
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
    def __init__(self, current: TypedIterator[int]) -> None:
        self.current = current


def numbers():
    yield 9
    yield 10


def drain(iterator: TypedIterator[int]) -> list[int]:
    return list(iterator)


def retained() -> TypedIterator[int]:
    values = [31, 32]
    return int_iterator(values)


def words() -> TypedIterator[str]:
    iterator = iter(["red", "blue"])

    def advance() -> str:
        return next(iterator)

    return TypedIterator(advance)


streams: list[TypedIterator[int]] = [
    int_iterator([1, 2]), int_iterator((3, 4)),
    int_iterator(Counter(2)), int_iterator(numbers()),
]
contents = [drain(iterator) for iterator in streams]
assert contents == [[1, 2], [3, 4], [1, 0], [9, 10]]
print("mixed", contents)

slot = Slot(int_iterator([8]))
assert drain(slot.current) == [8]
slot.current = int_iterator(Counter(2))
assert drain(slot.current) == [1, 0]
print("field replacement ok")

source = iter([10, 20, 30, 40, 50])
assert next(source) == 10
left = int_iterator(source)
right = int_iterator(source)
assert iter(left) is left
assert [next(left), next(source), next(right), next(left)] == [20, 30, 40, 50]
assert next(right, -1) == -1 and next(left, -1) == -1
print("partial consumption and shared source ok")

events: list[str] = []
observed = int_iterator(Observed(events))
assert events == ["iter"]
caught = False
try:
    next(observed)
except ValueError as error:
    assert str(error) == "source failed"
    caught = True
assert caught and events == ["iter", "next"]
assert next(observed) == 17
assert next(observed, -1) == -1
assert next(observed, -1) == -1
assert events == ["iter", "next", "next", "next", "next"]
print("lazy calls and exceptions", events)

values = [1]
live = int_iterator(values)
values.append(2)
assert next(live) == 1
values[1] = 3
assert next(live) == 3
assert next(live, -1) == -1
values.append(4)
assert next(live, -1) == -1
print("live mutation and exhaustion ok")

kept: list[TypedIterator[int]] = [retained(), int_iterator(numbers())]
assert [drain(iterator) for iterator in kept] == [[31, 32], [9, 10]]
text = words()
assert list(text) == ["red", "blue"]
print("retained closures and typed strings ok")
