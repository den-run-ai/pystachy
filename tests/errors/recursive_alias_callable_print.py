# error: recursive_alias_callable_print.py:13: error: printing a function, or comparing containers of functions, is not supported
# A function type that names a recursive alias is reported as any function type is.
from collections.abc import Callable

type V = int | list[V]


def f(x: V) -> int:
    return 1


h: Callable[[V], int] = f
print(h)
