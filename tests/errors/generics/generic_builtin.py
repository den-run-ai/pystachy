# error: Apply() cannot bind its type variables from the argument for 'fn', a <built-in function len>: a <built-in function len> is no def, lambda or Callable, whose signature Callable[[...], R] matches
from typing import Callable, Generic, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class Apply(Generic[T, R]):
    def __init__(self, fn: Callable[[T], R], x: T) -> None:
        self.result: R = fn(x)


print(Apply(len, "four").result)
