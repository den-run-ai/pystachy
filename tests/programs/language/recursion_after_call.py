# A successful source call leaves room for later leaf calls, even when a valid
# limit reduction follows it. A cloned leaf's terminal path must still publish
# exactly one frame before its observer. Calibrate spare frames independently
# of CPython's and the native runtime's entry-depth conventions.
import sys

events: list[int] = [0, 0, 0, 0, 0, 0]
configured = 60


def leaf(value: int) -> int:
    events[1] += 1
    return value + 1


def recursive(n: int) -> int:
    if n == 0:
        return 0
    return recursive(n - 1) + 1


def problem() -> ValueError:
    events[3] += 1
    return ValueError("terminal observer")


def cold(value: int) -> int:
    events[2] += 1
    if value < 0:
        raise problem()
    return value + 1


def after_call(n: int, value: int) -> int:
    events[0] += 1
    result = leaf(0)
    for i in range(n):
        result += cold(value)
        result += recursive(i)
    return result


def minimum_limit() -> int:
    # The smallest accepted limit is one above this helper's active depth.
    # Its caller can lower that by one after this helper has returned.
    candidate = 2
    while True:
        try:
            sys.setrecursionlimit(candidate)
            events[4] += 1
            return candidate
        except RecursionError:
            candidate += 1


def lower_after_call(n: int) -> int:
    result = leaf(0)
    minimum = minimum_limit()
    sys.setrecursionlimit(minimum - 1)
    events[5] = minimum - 1
    for i in range(n):
        result += leaf(i)
    sys.setrecursionlimit(configured)
    return result


def boundary(n: int, spare: int, which: int) -> int:
    if n == 0:
        return -10
    try:
        result = boundary(n - 1, spare, which)
    except RecursionError:
        return 0
    if result < spare - 1:
        return result + 1
    if result == spare - 1:
        starts = events[0]
        leaves = events[1]
        children = events[2]
        problems = events[3]
        lowered = events[4]
        if which == 2:
            try:
                total = lower_after_call(3)
            except RecursionError:
                sys.setrecursionlimit(configured)
                return -5
            if (total == 7 and events[1] == leaves + 4 and events[4] == lowered + 1
                    and events[5] < configured and sys.getrecursionlimit() == configured):
                return spare
            return -6
        try:
            after_call(1, -1)
        except (RecursionError, ValueError):
            if (events[0] == starts + 1 and events[1] == leaves + 1
                    and events[2] == children + 1
                    and events[3] == problems + (1 if which == 1 else 0)):
                return spare
            return -1
        return -2
    return result


original = sys.getrecursionlimit()
sys.setrecursionlimit(configured)
for repeat in range(3):
    print("terminal last slot", boundary(100, 2, 0) == 2)
    print("terminal next slot", boundary(100, 3, 1) == 3)
    print("lowered limit", boundary(100, 3, 2) == 3)
    print("recovered", after_call(2, 1), lower_after_call(2))
sys.setrecursionlimit(original)
