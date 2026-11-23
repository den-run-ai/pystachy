# Iterator[T] and Iterable[T] in a Protocol's methods hold any iterator or iterable of T items.
from typing import Iterable, Iterator, Protocol


class Numbers(Protocol):
    def __iter__(self) -> Iterator[int]: ...


class Span:
    def __init__(self, lo: int, hi: int) -> None:
        self.lo = lo
        self.hi = hi

    def __iter__(self) -> Iterator[int]:
        n = self.lo
        while n < self.hi:
            yield n
            n += 1


class Record:
    # one class, whatever iterable it retains: CPython's retained Iterable[int]
    def __init__(self, origin: Numbers) -> None:
        self.origin = origin

    def total(self) -> int:
        return sum(self.origin)


class Feed(Protocol):
    def items(self) -> Iterable[str]: ...


class Fixed:
    def items(self) -> list[str]:
        return ["a", "b"]


class Pair:
    def items(self) -> tuple[str, ...]:
        return ("x", "y")


records = [Record([1, 2, 3]), Record((7, 8)), Record(range(3)), Record(Span(10, 13)), Record({5: "a", 6: "b"}), Record({4})]
print([r.total() for r in records])
print([list(r.origin) for r in records])
live = [1]
kept = Record(live)
live.append(2)
print(kept.total(), [x * 2 for x in kept.origin], sorted(kept.origin, reverse=True))
feeds: list[Feed] = [Fixed(), Pair()]
print([" ".join(f.items()) for f in feeds])
print([n for r in records for n in r.origin if n % 2 == 0])
