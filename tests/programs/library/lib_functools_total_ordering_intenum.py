# functools.total_ordering of an IntEnum: int's four ordering methods are the class's too, so
# CPython's decorator adds none. Only < runs the class's own method, which ranks a lower value
# higher; <=, > and >= compare the values as ints.
from enum import IntEnum
from functools import total_ordering


@total_ordering
class Priority(IntEnum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3

    def __lt__(self, other: "Priority") -> bool:
        return self.value > other.value


a, b = Priority.LOW, Priority.HIGH
print(a < b, a <= b, a > b, a >= b, b < a, b <= a, b > a, b >= a)
print(sorted([Priority.MEDIUM, Priority.HIGH, Priority.LOW]))
print(max(Priority.MEDIUM, Priority.LOW), min(Priority.MEDIUM, Priority.LOW))
