# Bounded fast paths must select the complete guarded path near the limit.
# A worst-case bound cannot raise before a preceding side effect or reject a
# zero-trip loop whose body would never call its leaf. Calibrate spare frames
# without depending on Python and native runtime adapter depth conventions.
import sys

seen: list[int] = [0, 0, 0, 0, 0]


def step(value: int) -> int:
    seen[1] += 1
    return value + 1


def batch(n: int) -> int:
    seen[0] += 1
    result = 0
    for i in range(n):
        result = step(result)
    seen[2] += 1
    return result


def middle(value: int) -> int:
    seen[3] += 1
    return step(value)


def outer(value: int) -> int:
    seen[4] += 1
    return middle(value)


def one_spare(n: int) -> int:
    if n == 0:
        return -10
    try:
        result = one_spare(n - 1)
    except RecursionError:
        return 0
    if result == 0:
        starts = seen[0]
        leaves = seen[1]
        finishes = seen[2]
        empty = batch(0)
        try:
            batch(1)
        except RecursionError:
            if empty == 0 and seen[0] == starts + 2 and seen[1] == leaves and seen[2] == finishes + 1:
                return 1
            return -1
        return -2
    return result


def two_spare(n: int) -> int:
    if n == 0:
        return -10
    try:
        result = two_spare(n - 1)
    except RecursionError:
        return 0
    if result == 0:
        return 1
    if result == 1:
        leaves = seen[1]
        middles = seen[3]
        outers = seen[4]
        try:
            outer(3)
        except RecursionError:
            if seen[1] == leaves and seen[3] == middles + 1 and seen[4] == outers + 1:
                return 2
            return -1
        return -2
    return result


original = sys.getrecursionlimit()
sys.setrecursionlimit(60)
for repeat in range(3):
    print("one spare", one_spare(100) == 1)
    print("two spare", two_spare(100) == 2)
    print("recovered", batch(4), outer(7))
sys.setrecursionlimit(original)
