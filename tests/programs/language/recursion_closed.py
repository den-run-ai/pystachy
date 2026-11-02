# Closed recursion (#988): cycles that call only each other and functions that cannot recur
# count each frame at the same call as CPython does, from module code, through a function
# value and below a counted caller; with handlers inside the cycle, uncounted helpers with
# handlers of their own, plain generators, tail calls and exceptions that leave the cycle.
# (Depths are chosen so that the uncounted helpers never run in a frame CPython would refuse:
# tests/deviations/recursion_uncounted_frames.py.)
import sys
from collections.abc import Callable, Iterator


def down(n: int) -> int:
    if n == 0:
        return 0
    return down(n - 1) + 1


def even(n: int) -> bool:
    return True if n == 0 else odd(n - 1)


def odd(n: int) -> bool:
    return False if n == 0 else even(n - 1)


def tail(n: int, stop: int) -> int:
    if n == stop:
        return n
    return tail(n + 1, stop)


def guarded(n: int) -> int:
    # its own handler, in a helper that cannot recur
    try:
        return 10 // n
    except ZeroDivisionError:
        return -1


def through_helper(n: int) -> int:
    if n == 0:
        return guarded(0)
    return through_helper(n - 1) + guarded(n) * 0


def squares(n: int) -> Iterator[int]:
    for i in range(n):
        yield i * i


def through_generator(n: int) -> int:
    if n == 0:
        return 0
    total = 0
    for v in squares(3):
        total += v
    return through_generator(n - 1) + total - 5


def climb(n: int) -> int:
    # (a negative n returns at once: a probe of the cycle) the depth below this frame where a call
    # failed, times 10, + 1 if there one more call of the cycle failed again before its body
    # ran, + 2 if one frame up such a call had room
    if n < 0:
        return 0
    try:
        below = climb(n + 1)
    except RecursionError:
        try:
            climb(-1)
            return n * 10
        except RecursionError:
            return n * 10 + 1
    if below % 10 == 1 and below // 10 == n + 1:
        try:
            climb(-1)
            return below + 2
        except RecursionError:
            return below
    return below


def blow(n: int) -> int:
    if n == 30:
        raise ValueError("deep")
    return blow(n + 1) + 1


def ping(n: int) -> int:
    return pong(n + 1)


def pong(n: int) -> int:
    return ping(n + 1)


def counted_caller(n: int, f: Callable[[int], int]) -> int:
    # counts as it may call a function value; three frames above its deepest, a closed cycle
    # gets exactly the frames left
    if n < 0:
        return f(0)
    try:
        below = counted_caller(n + 1, f)
    except RecursionError:
        return 0
    if below == 3:
        for k in range(6):
            try:
                down(k)
            except RecursionError:
                return 100 + k
    return below + 1 if below < 100 else below


def attempt(f: Callable[[int], int], n: int) -> str:
    try:
        return str(f(n))
    except RecursionError:
        return "RecursionError"


original = sys.getrecursionlimit()
sys.setrecursionlimit(60)
for n in (56, 57, 58):
    print("down", n, attempt(down, n))
for n in (57, 58, 59):
    try:
        print("even", n, even(n), odd(n))
    except RecursionError:
        print("even", n, "RecursionError")
for stop in (57, 58, 59):
    try:
        print("tail", stop, tail(0, stop))
    except RecursionError:
        print("tail", stop, "RecursionError")
print("helper", attempt(through_helper, 56), attempt(through_helper, 58))
print("generator", attempt(through_generator, 57), attempt(through_generator, 58))
value: Callable[[int], int] = down
print("value", attempt(value, 57), attempt(value, 58))
print("climb", climb(0))
try:
    blow(0)
except ValueError as e:
    print("escaped", e, attempt(down, 57), attempt(down, 58))
try:
    ping(0)
except RecursionError:
    print("unbounded caught")
ident: Callable[[int], int] = lambda k: k
print("below counted", counted_caller(0, ident), attempt(down, 57))
sys.setrecursionlimit(original)
print(sys.getrecursionlimit() == original, down(500))
