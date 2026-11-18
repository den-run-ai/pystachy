# functools.total_ordering: the methods it adds for each of the four a class may define, the
# class's own ones kept, an enum class, and the three ways a module names the decorator.
import enum
import functools
import functools as ft
from functools import total_ordering as ordered


@ordered
class ByLt:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ByLt) and self.n == other.n

    def __lt__(self, other: "ByLt") -> bool:
        return self.n < other.n


@functools.total_ordering
class ByLe:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ByLe) and self.n == other.n

    def __le__(self, other: "ByLe") -> bool:
        return self.n <= other.n


@ft.total_ordering
class ByGt:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ByGt) and self.n == other.n

    def __gt__(self, other: "ByGt") -> bool:
        return self.n > other.n


@ordered
class ByGe:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, that: object) -> bool:
        return isinstance(that, ByGe) and self.n == that.n

    def __ge__(me, that: "ByGe") -> bool:
        return me.n >= that.n


@ordered
class Both:
    # __lt__ is the root; __ge__ is the class's own and is kept
    def __init__(self, n: int) -> None:
        self.n = n
        self.asked: list[str] = []

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Both) and self.n == other.n

    def __lt__(self, other: "Both") -> bool:
        self.asked.append("lt")
        return self.n < other.n

    def __ge__(self, other: "Both") -> bool:
        self.asked.append("ge")
        return self.n >= other.n


@ordered
class Grade(enum.Enum):
    LOW = 1
    MID = 2
    HIGH = 3

    def __lt__(self, other: "Grade") -> bool:
        return self.value < other.value


def table(a, b) -> list[bool]:
    return [a < b, a <= b, a > b, a >= b, b < a, b <= a, b > a, b >= a, a <= a, a >= a, a < a, a > a]


print(table(ByLt(1), ByLt(2)))
print(table(ByLe(1), ByLe(2)))
print(table(ByGt(1), ByGt(2)))
print(table(ByGe(1), ByGe(2)))
x, y = Both(1), Both(2)
print(table(x, y), x.asked, y.asked)
print(table(Grade.LOW, Grade.HIGH), sorted([Grade.HIGH, Grade.LOW, Grade.MID]), max(Grade.MID, Grade.LOW))
print(sorted([ByLt(3), ByLt(1), ByLt(2)], reverse=True)[0].n, min(ByGe(4), ByGe(2)).n)
