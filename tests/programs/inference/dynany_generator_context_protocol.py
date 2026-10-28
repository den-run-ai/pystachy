# pystachy: dynamic-any
# A concrete yield context must leave the send and return channels independent.
from typing import Any, Generator


def inner() -> Generator[list[Any], list[int] | None, list[int] | None]:
    try:
        sent = yield [1, 2]
        if sent is not None:
            sent.append(4)
        return sent
    finally:
        print("inner cleanup")


def outer() -> Generator[list[int], list[int] | None, None]:
    result = yield from inner()
    print("result", result)


it = outer()
row = next(it)
alias = row
row.append(3)
try:
    it.send(alias)
except StopIteration:
    print("done", row is alias, row)

closed = outer()
print(next(closed))
closed.close()

thrown = outer()
print(next(thrown))
try:
    thrown.throw(ValueError("stop"))
except ValueError as error:
    print("caught", error)


def dynamic_return() -> Generator[list[Any], None, list[Any]]:
    yield [8]
    return [9]


def return_outer() -> Generator[list[int], None, None]:
    result = yield from dynamic_return()
    result.append("still dynamic")
    print("return channel", result)


print(list(return_outer()))
