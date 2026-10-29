# pystachy: dynamic-any
from typing import Any


def numbers():
    print("start")
    yield 2
    print("middle")
    yield 4
    print("end")


g = numbers()
a: Any = g
b: Any = g
print("identity", a is b, id(a) == id(b), a == b)
print("iterator", iter(a) is a)
print(next(a))
print(next(g))
print(next(b, "done"))
print(next(a, None), next(g, None))

expression: Any = (i * i for i in range(4))
print(list(expression), list(expression))


def values():
    value: Any = None
    yield value
    value = "snow 雪"
    yield value
    value = 2.5
    yield value


v: Any = values()
print(next(v), next(v), next(v), next(v, "end"))
print(type(v).__name__, type(v) is type(a))
print(hash(a) == hash(b), len({a: 1, b: 2}))


def lists():
    xs: list[Any] = [1, "two"]
    yield xs
    print("mutated", xs)
    yield xs


items: Any = lists()
first = next(items)
first.append(3)
second = next(items)
print(first is second, second)
print(next(items, False))
