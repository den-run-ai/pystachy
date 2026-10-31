# Share equivalent terminal child calls reached through distinct branches.
# Earlier effects and cold-path publication must survive the shared tail.
# A partial fast region must publish every omitted source frame before an
# observer. Calibrate spare frames without assuming CPython/native offsets.
import sys

events: list[int] = [0, 0, 0, 0, 0]
configured = 60


def make_error() -> ValueError:
    events[2] += 1
    return ValueError("cold observer")


def cold_leaf(value: int) -> int:
    events[1] += 1
    if value < 0:
        raise make_error()
    if value == 0:
        return 9 // value
    return value + 1


def tail_observer() -> int:
    events[3] += 1
    try:
        sys.setrecursionlimit(configured)
    except RecursionError:
        events[4] += 1
    return 17


def partial(tail: bool, value: int) -> int:
    events[0] += 1
    if tail:
        return tail_observer()
    if value <= 0:
        return cold_leaf(value)
    return cold_leaf(value)


def probe(depth: int, which: int) -> int:
    if depth == 0:
        return -10
    try:
        result = probe(depth - 1, which)
    except RecursionError:
        return 0
    if result == 0:
        return 1
    if result == 1 and which == 2:
        return 2
    if result == 2 and which == 2:
        roots = events[0]
        children = events[1]
        errors = events[2]
        try:
            partial(False, -1)
        except (RecursionError, ValueError):
            # The error helper's body fits in the third spare frame. CPython
            # may exhaust while constructing its exception, after this effect.
            if events[0] == roots + 1 and events[1] == children + 1 and events[2] == errors + 1:
                return 3
            return -5
        return -6
    if result == 1:
        roots = events[0]
        children = events[1]
        errors = events[2]
        tails = events[3]
        limit_errors = events[4]
        if which == 3:
            try:
                partial(False, 0)
            except ZeroDivisionError:
                if events[0] == roots + 1 and events[1] == children + 1 and events[2] == errors:
                    return 2
                return -7
            except RecursionError:
                return -8
            return -9
        if which == 0:
            try:
                partial(False, -1)
            except RecursionError:
                if events[0] == roots + 1 and events[1] == children + 1 and events[2] == errors:
                    return 2
                return -1
            except ValueError:
                return -2
            return -3
        value = partial(True, 0)
        if value == 17 and events[0] == roots + 1 and events[3] == tails + 1 and events[4] == limit_errors + 1:
            return 2
        return -4
    return result


original = sys.getrecursionlimit()
sys.setrecursionlimit(configured)
for repeat in range(3):
    print("cold offset", probe(100, 0) == 2)
    print("tail depth", probe(100, 1) == 2)
    print("cold positive", probe(100, 2) == 3)
    print("hidden failure", probe(100, 3) == 2)
    print("recovered", partial(False, 2))
sys.setrecursionlimit(original)
try:
    partial(False, -1)
except ValueError:
    print("cold observer", events[2] == 4)
