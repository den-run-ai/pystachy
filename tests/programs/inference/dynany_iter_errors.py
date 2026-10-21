# pystachy: dynamic-any
# Iterating objects through Any values raises what CPython raises (#773): an __iter__ that returns
# no iterator, an exception that __next__ raises other than StopIteration, and an object without
# __iter__.
from typing import Any


class Bad:
    def __init__(self) -> None:
        self.items = [1, 2]

    def __iter__(self):
        return self.items


class Boom:
    def __init__(self) -> None:
        self.i = 0

    def __iter__(self) -> "Boom":
        return self

    def __next__(self) -> int:
        self.i += 1
        if self.i == 2:
            raise ValueError("boom at 2")
        return self.i


class NoIter:
    pass


def attempt(what: str, x: Any) -> None:
    try:
        for v in x:
            print(what, v)
    except (TypeError, ValueError) as e:
        print(what, type(e).__name__ + ":", e)


attempt("bad", Bad())
attempt("boom", Boom())
attempt("none", NoIter())
b: Any = Boom()
try:
    print(list(b))
except ValueError as e:
    print("list ValueError:", e)
