# pystachy: dynamic-any
# pystachy: python-int
from typing import Any


def check(needle: Any) -> None:
    big = 2 ** 70
    values: list[int] = [-2 ** 63, big, big + 1, big]
    print(needle in values, needle not in values, values.count(needle))
    try:
        print(values.index(needle), values.index(needle, 2, 4))
    except ValueError as error:
        print(error)
    try:
        values.remove(needle)
        print(values)
    except ValueError as error:
        print(error)


queries: list[Any] = [2 ** 70, float(2 ** 70), -2 ** 63, None, "missing", True]
for query in queries:
    check(query)


def check_float(needle: Any) -> None:
    values: list[float] = [1.0, float(2 ** 70), float(2 ** 70)]
    print(needle in values, values.count(needle))
    try:
        print(values.index(needle))
        values.remove(needle)
        print(len(values))
    except ValueError as error:
        print(error)


check_float(2 ** 70)
check_float(2 ** 70 + 1)
check_float(None)


class Match:
    def __eq__(self, other: Any) -> bool:
        print("compare", other)
        return other == 2 ** 70


values: list[int] = [1, 2 ** 70, 3]
matcher: Any = Match()
print(matcher in values, values.count(matcher), values.index(matcher))
values.remove(matcher)
print(values)


class Shrink:
    def __init__(self, values: list[int]) -> None:
        self.values = values

    def __eq__(self, other: Any) -> bool:
        print("shrink", other)
        self.values.clear()
        return False


shrinker: Any = Shrink(values)
print(shrinker in values, values)


class Fail:
    def __eq__(self, other: Any) -> bool:
        raise ValueError("comparison ran")


failure: Any = Fail()
try:
    print(failure in [2 ** 70])
except ValueError as error:
    print(error)
