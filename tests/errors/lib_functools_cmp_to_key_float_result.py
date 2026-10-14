# error: expected int, got float
# CPython allows numeric comparator results beyond int. This typed port
# supports int-returning comparators only, and rejects float without truncation.
from functools import cmp_to_key


def compare(x: int, y: int) -> float:
    return float(x - y)


print(sorted([3, 1, 2], key=cmp_to_key(compare)))
