# pystachy: dynamic-any
# Runtime expansion does not imply variadic targets, arbitrary mappings, or new layouts.
from typing import Any, Callable


def variadic(*values: int) -> int:
    return sum(values)


def identity(value: int) -> int:
    return value


class Mapping:
    def keys(self) -> list[str]:
        return ["value"]

    def __getitem__(self, key: str) -> int:
        return 7


class Record:
    def __init__(self, value: int) -> None:
        self.value = value

    def read(self) -> int:
        return self.value


def attempt(label: str, function: Any, args: Any, kwargs: Any) -> None:
    try:
        print(label, function(*args, **kwargs))
    except NotImplementedError as error:
        print(label, str(error))


target: Any = variadic
attempt("variadic", target, [1, 2], {})
function: Any = identity
attempt("mapping", function, [], Mapping())
typed: Callable[[int], int] = identity
erased: Any = typed
attempt("erased", erased, [8], {})
items: Any = []
one: Any = [9]
try:
    items.append(*one)
    print("builtin", items)
except NotImplementedError as error:
    print("builtin", str(error))
factory: Any = Record
try:
    print("class", factory(*one).value)
except NotImplementedError as error:
    print("class", str(error))
