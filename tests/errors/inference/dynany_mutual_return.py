# error: even() returns both int and Any (each function has one return type)
# pystachy: dynamic-any
# even() returns an int, then an Any value, which would make it return Any; but odd(), compiled
# for its call while even() was, has already taken even()'s int (functions that call each other):
# what even() returns stays decided, and the second return is an error.
from typing import Any


def even(n, x: Any):
    if n == 0:
        return 1
    return odd(n - 1, x)


def odd(n, x: Any):
    if n == 0:
        return x
    return even(n - 1, x)


print(even(3, "s"))
