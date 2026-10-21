# A generic def's **P and *Ts are type parameters of its own in its nested defs too (#505): a
# decorator's wrapper forwards *args: P.args and **kwargs: P.kwargs, also past Concatenate, and
# a nested def's *xs: *Ts forwards the outer def's.
from collections.abc import Callable
from typing import Concatenate


def logged[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        print("call", fn.__name__)
        return fn(*args, **kwargs)

    return wrapper


@logged
def add(a: int, b: int = 2) -> int:
    return a + b


@logged
def greet(name: str, *, punct: str = "!") -> str:
    return "hi " + name + punct


def with_base[**P, R](fn: Callable[Concatenate[int, P], R]) -> Callable[P, R]:
    def call(*args: P.args, **kwargs: P.kwargs) -> R:
        return fn(10, *args, **kwargs)

    return call


def scaled(base: int, k: int) -> int:
    return base * k


def forward[*Ts](f: Callable[[*Ts], int], *args: *Ts) -> int:
    def go(*xs: *Ts) -> int:
        return f(*xs)

    return go(*args)


print(add(1), add(1, b=5), greet("bo"), greet("al", punct="?"))
print(with_base(scaled)(3), forward(scaled, 4, 5))
