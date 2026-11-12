# pystachy: dynamic-any
from typing import Any, Generator

number = int("1000")
original: Any = number


def closes():
    try:
        yield 1
    except GeneratorExit:
        print("closing")
        return number
    return 0


g = closes()
print(next(g))
result = g.close()
print(result, result is original, g.close())
try:
    next(g)
except StopIteration as error:
    print(error.args, error.value)

new = closes()
print("new", new.close())
try:
    next(new)
except StopIteration as error:
    print(error.args, error.value)


def direct():
    yield 2
    return number


fast = direct()
print(next(fast), fast.close(), fast.close())


def rebound() -> Generator[int, None, int | None]:
    global number
    try:
        yield 3
    finally:
        try:
            return number
        finally:
            number = int("2000")


r = rebound()
print(next(r))
result = r.close()
print(result, result is original, number)


def failing():
    try:
        yield 4
    finally:
        raise ValueError("close failed")


f = failing()
print(next(f))
try:
    print(f.close())
except ValueError as error:
    print(error.args)
print(f.close())
