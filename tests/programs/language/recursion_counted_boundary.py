# Recursive source functions count at the limit as CPython's frames do (#988). In the deepest
# frame that caught RecursionError, a recursive call fails after its arguments are evaluated
# and before its body runs, directly or through a callback; one frame up it gets exactly one
# more frame. Only recursive functions run near the limit here: the native policy does not
# count functions that cannot be entered again while active (tests/deviations/recursion_uncounted_frames.py).
import sys
from collections.abc import Callable

args: list[int] = []
bodies: list[int] = [0]


def countdown(n: int) -> int:
    bodies[0] += 1
    if n <= 0:
        return 0
    return countdown(n - 1) + 1


def even(n: int) -> bool:
    bodies[0] += 1
    return True if n == 0 else odd(n - 1)


def odd(n: int) -> bool:
    bodies[0] += 1
    return False if n == 0 else even(n - 1)


def deepest(n: int, f: Callable[[int], int]) -> int:
    try:
        return deepest(n + 1, f)
    except RecursionError:
        failed = 0
        for attempt in range(3):
            before = bodies[0]
            args.append(attempt)
            try:
                if attempt == 0:
                    countdown(args.pop())
                elif attempt == 1:
                    even(args.pop())
                else:
                    f(args.pop())
            except RecursionError:
                if len(args) == 0 and bodies[0] == before:
                    failed += 1
        return failed


def one_spare(n: int) -> int:
    try:
        result = one_spare(n + 1)
    except RecursionError:
        return -1
    if result == -1:
        before = bodies[0]
        try:
            countdown(1)
        except RecursionError:
            return bodies[0] - before
        return -2
    return result


original = sys.getrecursionlimit()
sys.setrecursionlimit(60)
for repeat in range(3):
    print("deepest", deepest(0, countdown))
    print("one spare", one_spare(0))
    print("recovered", countdown(10), even(10), odd(7))
sys.setrecursionlimit(original)
print(sys.getrecursionlimit() == original)
