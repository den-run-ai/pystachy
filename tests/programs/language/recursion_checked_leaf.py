# A previous successful child can prove another leaf check redundant, but a
# function entry or a loop backedge cannot prove that the FIRST child fits.
import sys

seen: list[int] = [0, 0, 0, 0]
pending: list[int] = []


def step(value: int) -> int:
    seen[1] += 1
    return value + 1


def recursive(n: int) -> int:
    if n == 0:
        return 0
    return recursive(n - 1) + 1


def batch(n: int) -> int:
    seen[0] += 1
    result = 0
    for i in range(n):
        result += step(pending.pop())
        result += step(1)
        result += recursive(i)
    seen[2] += 1
    return result


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
        before = len(pending)
        pending.append(7)
        empty = batch(0)
        try:
            batch(1)
        except RecursionError:
            if (empty == 0 and seen[0] == starts + 2 and seen[1] == leaves
                    and seen[2] == finishes + 1 and len(pending) == before):
                return 1
            return -1
        return -2
    return result


def problem() -> ValueError:
    seen[3] += 1
    return ValueError("cold child")


def cold(value: int) -> int:
    if value < 0:
        raise problem()
    return value + 1


def warmed(n: int, negative: bool) -> int:
    result = step(0)
    for i in range(n):
        result += cold(-1 if negative else i)
        result += recursive(i)
    return result


original = sys.getrecursionlimit()
sys.setrecursionlimit(60)
for repeat in range(3):
    print("first call", one_spare(100) == 1)
    pending.extend([2, 3, 4])
    print("recovered", batch(3), warmed(3, False))
sys.setrecursionlimit(original)
try:
    warmed(1, True)
except ValueError as error:
    print("cold", str(error), seen[3] == 1)
print("after cold", warmed(3, False))
