# pystachy: dynamic-any
# Boxing delegated yields preserves send/return values, close(), and throw().
from typing import Any, Generator


def integers() -> Generator[int, str | None, str]:
    try:
        sent = yield 1
        print("sent", sent)
        try:
            yield 2
        except ValueError as error:
            print("recovered", error)
            yield 3
        return "complete"
    finally:
        print("cleanup")


def boxed() -> Generator[Any, str | None, None]:
    result = yield from integers()
    print("returned", result)


it = boxed()
print(next(it), it.send("hello"))
print(it.throw(ValueError("continue")))
try:
    next(it)
except StopIteration:
    print("done")

closed = boxed()
print(next(closed))
closed.close()
