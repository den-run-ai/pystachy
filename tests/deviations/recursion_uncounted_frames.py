# Documented deviation (docs/language/compatibility.md#errors-and-control-flow): only functions
# that recursion can repeat count toward sys.setrecursionlimit(). A function that cannot be
# entered again while it is active (here, helpers that call only what the compiler sees, and a
# generator whose body cannot) runs in the deepest frame, where CPython counts its frame too
# and raises RecursionError, and does not raise the depth that sys.setrecursionlimit()
# compares a new limit with.
import sys
from collections.abc import Iterator

calls: list[int] = [0]


def helper(n: int) -> int:
    calls[0] += 1
    return n + 1


def deepest(n: int) -> int:
    try:
        return deepest(n + 1)
    except RecursionError:
        try:
            return helper(0)
        except RecursionError:
            return -1


def outer() -> bool:
    return middle()


def middle() -> bool:
    return inner()


def inner() -> bool:
    try:
        sys.setrecursionlimit(3)
    except RecursionError:
        return False
    sys.setrecursionlimit(60)
    return True


def numbers() -> Iterator[int]:
    yield 1
    yield 2


stream = numbers()


def deepest_resume(n: int) -> int:
    try:
        return deepest_resume(n + 1)
    except RecursionError:
        try:
            return next(stream)
        except RecursionError:
            return -1


sys.setrecursionlimit(60)
print(deepest(0), calls[0])
print(outer(), sys.getrecursionlimit())
print(deepest_resume(0), next(stream, -2))
