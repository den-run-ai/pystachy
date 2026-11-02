# Every counted entry compares the depth with one threshold, the trip: the lower of the limit and
# the depth that the native stack is known to hold (an 8 MiB stack's is near the default limit),
# and only an entry at or past it checks the limit and the stack's floor. sys.setrecursionlimit()
# moves the trip both ways: lowered, raised past that depth and lowered again, the limit fails
# exactly where CPython's does (at the same depth, directly and through a function value; the
# deepest frame that caught RecursionError cannot call a recursive function, and one frame up can
# make exactly one call), and a recursion or a chain of generator resumes past it that the limit
# allows completes. Nothing printed depends on the stack's size.
import sys
from collections.abc import Callable, Iterator

bodies: list[int] = [0]
hops: list[Callable[[int], int]] = []


def countdown(n: int) -> int:
    bodies[0] += 1
    if n <= 0:
        return 0
    return countdown(n - 1) + 1


def reach(n: int) -> int:
    try:
        return reach(n + 1)
    except RecursionError:
        return n


def hop(n: int) -> int:
    # (through a function value: the entry keeps the depth word, unlike reach's closed recursion)
    try:
        return hops[0](n + 1)
    except RecursionError:
        return n


def deepest(n: int) -> int:
    try:
        return deepest(n + 1)
    except RecursionError:
        before = bodies[0]
        try:
            countdown(0)
        except RecursionError:
            return 1 if bodies[0] == before else -2
        return -1


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


def nest(n: int) -> Iterator[int]:
    # (each level resumes the next: a counted resume's entry)
    if n == 0:
        yield 0
        return
    for v in nest(n - 1):
        yield v + 1


hops.append(hop)
original = sys.getrecursionlimit()
for limit in (60, 3000, 100, 2500, 1000):
    sys.setrecursionlimit(limit)
    print(sys.getrecursionlimit(), "reached", reach(0), hop(0), "deepest", deepest(0), "one spare", one_spare(0))
sys.setrecursionlimit(3000)
print("past it", countdown(2500), sum(nest(1200)))
try:
    print(countdown(5000))
except RecursionError:
    print("countdown caught")
try:
    print(sum(nest(5000)))
except RecursionError:
    print("nest caught")
print("recovered", countdown(10), sum(nest(10)))
sys.setrecursionlimit(original)
print(sys.getrecursionlimit() == original)
