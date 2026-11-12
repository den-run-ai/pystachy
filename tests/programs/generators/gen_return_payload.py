# pystachy: dynamic-any
from typing import Any, Generator

number = int("1000")
original: Any = number


def values(value: int):
    yield 1
    return value


def finish(g) -> Any:
    try:
        print("unexpected", next(g))
    except StopIteration as error:
        print(error.args, error.value)
        return error.value
    return None


g = values(number)
print(next(g))
print(finish(g) is original)
print(finish(g) is None)
print(g.close())

boxed: Any = values(number)
print(next(boxed))
try:
    next(boxed)
except StopIteration as error:
    print("boxed", error.args, error.value is original)
try:
    next(boxed)
except StopIteration as error:
    print("boxed again", error.args, error.value is None)

h = values(number)
print(next(h), next(h, -1))
print(finish(h) is None)


def delegated():
    result = yield from values(number)
    return result + 1


d = delegated()
print(next(d))
print(finish(d))


def sent() -> Generator[int, Any, Any]:
    item = yield 2
    return item


s = sent()
print(next(s))
try:
    s.send(original)
except StopIteration as error:
    print("send", error.args, error.value is original)
try:
    s.send(None)
except StopIteration as error:
    print("send again", error.args, error.value is None)


def handled():
    try:
        yield 3
    except ValueError:
        return number
    return 0


t = handled()
print(next(t))
try:
    t.throw(ValueError("finish"))
except StopIteration as error:
    print("throw", error.args, error.value is original)
print(finish(t) is None)


def identity(x: int) -> int:
    return x


m = map(identity, values(number))
print(next(m))
print(finish(m) is original)


def empty():
    yield 4
    return None


n = empty()
print(next(n))
print(finish(n) is None)
