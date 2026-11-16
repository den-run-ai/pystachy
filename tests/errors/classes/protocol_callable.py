# error: protocol_callable.py:14: error: expected Handler, got Callable[[int], str]: a Callable[[int], str] is not an implementation: annotate a callback with Callable[[A], R] rather than a protocol with __call__
from typing import Callable, Protocol


class Handler(Protocol):
    def __call__(self, x: int) -> str: ...


def show(x: int) -> str:
    return str(x)


f: Callable[[int], str] = show
h: Handler = f
print(h(1))
