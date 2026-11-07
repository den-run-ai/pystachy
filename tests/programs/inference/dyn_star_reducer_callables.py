# pystachy: dynamic-any
# One runtime pack serves fixed functions, closures, methods and callable objects.
from typing import Any


def add(a: int, b: int = 20, *, c: int = 3) -> int:
    return a + b + c


def make(prefix: str) -> Any:
    def join(a: str, b: str = "!") -> str:
        return prefix + a + b
    return join


class Scale:
    def __init__(self, factor: int) -> None:
        self.factor = factor

    def apply(self, a: int, b: int = 1) -> int:
        return self.factor * (a + b)

    def __call__(self, a: int, b: int = 1) -> int:
        return self.apply(a, b)


def invoke(function: Any, args: Any, kwargs: Any) -> Any:
    return function(*args, **kwargs)


scale = Scale(5)
handlers: list[Any] = [add, make("prefix:"), scale.apply, scale]
packs: list[Any] = [[1, 2], ("value",), [3, 4], (6,)]
for index in range(len(handlers)):
    print(invoke(handlers[index], packs[index], {}))
print(invoke(handlers[0], [8], {"b": 2, "c": 4}))
print(invoke(handlers[1], (), {"a": "named", "b": "?"}))

function: Any = add
first: Any = [1]
second: Any = (2,)
empty: Any = []
print(function(*first, *second, c=5))
print(function(*empty, 3, *second, c=6))
print(function(4, *empty, b=7, c=8))
print(function(*range(1, 3), c=9))

# Keyword groups preserve their order while forwarding differently typed values.
kw1: Any = {"b": 10}
kw2: dict[str, int] = {"c": 11}
print(function(*first, **kw1, **kw2))
