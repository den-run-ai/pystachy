# Closed recursion (#988, docs/internals.md#native-recursion-depth): down and the even/odd cycle
# call only each other and a helper that cannot recur, so their bodies (@r.*) check the depth
# their caller passed without loading or storing the depth word, which only their symbols load.
# through calls a function value: it keeps the word current, loading and storing it.
from collections.abc import Callable


def helper(n: int) -> int:
    return n * 3 + 1


def down(n: int) -> int:
    if n == 0:
        return 0
    return down(n - 1) + helper(n)


def even(n: int) -> bool:
    return True if n == 0 else odd(n - 1)


def odd(n: int) -> bool:
    return False if n == 0 else even(n - 1)


def through(f: Callable[[int], int], n: int) -> int:
    if n == 0:
        return f(0)
    return through(f, n - 1) + 1


print(down(5), even(6), odd(6), through(helper, 4))
