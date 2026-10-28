# pystachy: dynamic-any
from typing import Any


def broken():
    value: Any = 1
    print("yield first")
    yield value
    value = "x"
    print("yield second")
    yield value
    print("late effect")
    raise ValueError("late failure")


class BrokenIterator:
    def __init__(self) -> None:
        self.index = 0

    def __iter__(self) -> "BrokenIterator":
        return self

    def __next__(self) -> Any:
        self.index += 1
        if self.index == 1:
            print("next first")
            return 1
        if self.index == 2:
            print("next second")
            return "x"
        if self.index == 3:
            print("late effect")
            raise ValueError("late failure")
        raise StopIteration


def failure(source: Any, maximum: bool) -> None:
    try:
        print(max(source) if maximum else min(source))
    except TypeError as error:
        print("comparison", error)
    except ValueError as error:
        print("wrong first error", error)
    # A failed comparison must leave the borrowed iterator at its second item.
    try:
        print("resume", next(source, "done"))
    except ValueError as error:
        print("resume error", error)
    print("end", next(source, "done"))


for maximum in [False, True]:
    print("generator", maximum)
    failure(broken(), maximum)
    print("object", maximum)
    failure(BrokenIterator(), maximum)


class Candidate:
    def __init__(self, rank: int, label: str) -> None:
        self.rank = rank
        self.label = label

    def __lt__(self, other: "Candidate") -> bool:
        print("less", self.label, other.label)
        return self.rank < other.rank

    def __gt__(self, other: "Candidate") -> bool:
        print("greater", self.label, other.label)
        return self.rank > other.rank


def candidates(first: Any, second: Any, third: Any):
    print("candidate first")
    yield first
    print("candidate second")
    yield second
    print("candidate third")
    yield third
    print("candidate end")


first: Any = Candidate(2, "first")
equal: Any = Candidate(2, "equal")
small: Any = Candidate(1, "small")
large: Any = Candidate(3, "large")
source: Any = candidates(first, equal, small)
print("minimum identity", min(source) is small)
source = candidates(first, equal, large)
print("maximum identity", max(source) is large)
source = candidates(first, equal, first)
print("tie identity", min(source) is first)
source = candidates(first, equal, first)
print("tie identity", max(source) is first)

empty: Any = []
single: Any = [None]
for maximum in [False, True]:
    try:
        print(max(empty) if maximum else min(empty))
    except ValueError as error:
        print("empty", error)
    print("singleton", max(single) if maximum else min(single))


def argument(label: str, value: Any) -> Any:
    print("argument", label)
    return value


def bad_argument() -> Any:
    print("argument failure")
    raise ValueError("argument failed")


# Multiple arguments are all evaluated before comparisons begin. A later
# argument failure therefore precedes an otherwise invalid earlier comparison.
for maximum in [False, True]:
    try:
        if maximum:
            print(max(argument("first", 1), argument("second", "x"), argument("third", 3)))
        else:
            print(min(argument("first", 1), argument("second", "x"), argument("third", 3)))
    except TypeError as error:
        print("arguments comparison", error)
    try:
        if maximum:
            print(max(argument("first", 1), argument("second", "x"), bad_argument()))
        else:
            print(min(argument("first", 1), argument("second", "x"), bad_argument()))
    except ValueError as error:
        print("arguments exception", error)
