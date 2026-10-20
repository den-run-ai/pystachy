# Generic deque construction preserves supported native iterable element types.
from collections import deque
import collections

print(deque("abc"), deque((1, 2, 3)), deque({"a": 1, "b": 2}))
print(sorted(deque({3, 1, 2})))
a = collections.deque[int]()
a.append(7)
b: deque[str] = deque([])
b.append("x")
print(a, b)


def empty() -> deque[int]:
    return deque()


def total(items: list[deque[int]]) -> int:
    return sum([sum(x) for x in items])


c = empty()
c.append(9)
print(c, total([deque([1, 2]), c]))

# Explicit union items use the current tagged-value operations inside a generic class.
values: deque[int | str] = deque()
values.append(2)
values.appendleft("a")
print(values, 2 in values, "a" in values, values.count(2))
print(values.popleft(), values.pop(), bool(values))

# Specialization does not evaluate arguments early, twice, or past an exception.
def items(n: int) -> list[int]:
    print("items", n)
    if n < 0:
        raise ValueError("items")
    return [n]


def bound(n: int) -> int:
    print("bound", n)
    return n


print(deque[int](items(3), maxlen=bound(2)))
try:
    deque[int](items(-1), maxlen=bound(1))
except ValueError as error:
    print(type(error).__name__, error)
