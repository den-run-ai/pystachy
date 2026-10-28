# pystachy: dynamic-any
# next()/throw() send implicit None; explicit sends preserve their Any values.
from typing import Any, Generator


def values() -> Generator[int, Any, None]:
    first = yield 1
    print("first", first is None, first)
    try:
        second = yield 2
        print("second", second is None, second)
    except ValueError:
        third = yield 3
        print("third", third is None, third)


def delegated() -> Generator[int, Any, None]:
    yield from values()


it = delegated()
print(next(it), next(it))
try:
    it.send(None)
except StopIteration:
    print("done")

it2 = delegated()
print(next(it2), it2.send("sent"))
print(it2.throw(ValueError("recover")))
try:
    next(it2)
except StopIteration:
    print("done after throw")
