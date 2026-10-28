# pystachy: dynamic-any
from typing import Any


def guarded():
    try:
        print("enter")
        yield 1
        print("resume")
        yield 2
    finally:
        print("cleanup")


g: Any = guarded()
for item in g:
    print(item)
    break
print("kept")
print(list(g))
print(list(g))
try:
    next(g)
except StopIteration:
    print("exhausted")


def broken():
    yield 3
    raise ValueError("body failed")


b: Any = broken()
print(next(b))
try:
    next(b, 99)
except ValueError as error:
    print(error)
print(next(b, 99))


def stop_inside():
    yield 4
    raise StopIteration("not exhaustion")


s: Any = stop_inside()
print(next(s))
try:
    next(s, 99)
except RuntimeError as error:
    print(error)
print(next(s, 99))
