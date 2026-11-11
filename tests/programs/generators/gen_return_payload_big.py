# pystachy: dynamic-any
# pystachy: python-int
from typing import Any

number = 10 ** 40
original: Any = number


def inner():
    yield 1
    return number


def outer():
    result = yield from inner()
    return result + 1


g = inner()
print(next(g))
try:
    next(g)
except StopIteration as error:
    print(error.args, error.value is original)
o = outer()
print(next(o))
try:
    next(o)
except StopIteration as error:
    print(error.value)
