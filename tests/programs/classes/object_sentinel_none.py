# object()'s object compared with == and != to a builtin value that may be None, where the sentinel
# may be None too: equal where both are None (CPython's None == None), else unequal
from typing import Callable

_MISSING = object()


def f() -> int:
    return 0


def nulls(flag: bool, n: int | None, x: float | None, h: Callable[[], int] | None, r: range | None, t: str | None, p: tuple[int, int] | None) -> None:
    s = _MISSING
    if not flag:
        s = None
    print(s == n, n == s, s != n, n != s, s == x, x != s)
    print(s == h, h != s, s == r, r == s, s == t, t != s, s == p, p != s)
    print(s == 1, 1 != s, s == None, None != s)


nulls(False, None, None, None, None, None, None)
nulls(True, None, None, None, None, None, None)
nulls(False, 3, 2.5, f, range(2), "a", (1, 2))
nulls(True, 3, 2.5, f, range(2), "a", (1, 2))
