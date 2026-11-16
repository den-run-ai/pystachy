# Exceptions raised by an implementation propagate through its table: StopIteration ends loops.
from typing import Iterator, Protocol


class Source(Protocol):
    def __iter__(self) -> Iterator[int]: ...

    def read(self, key: str) -> int: ...


class Failing:
    def __init__(self) -> None:
        self.calls = 0

    def __iter__(self) -> "Failing":
        return self

    def __next__(self) -> int:
        self.calls += 1
        if self.calls == 3:
            raise ValueError("third item failed")
        return self.calls

    def read(self, key: str) -> int:
        raise KeyError(key)


class Table:
    def __init__(self) -> None:
        self.data = {"a": 1}

    def __iter__(self) -> Iterator[int]:
        return iter([10, 20])

    def read(self, key: str) -> int:
        return self.data[key]


sources: list[Source] = [Table(), Failing()]
for s in sources:
    seen: list[int] = []
    try:
        for x in s:
            seen.append(x)
    except ValueError as e:
        print("stopped", seen, e)
    else:
        print("all", seen)
    try:
        print(s.read("a"))
    except KeyError as e:
        print("missing", e)
