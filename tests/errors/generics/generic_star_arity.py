# error: Memo.__call__() takes 3 positional arguments but 2 were given (its *args is a tuple[int,int])
from typing import Callable, Generic, TypeVar, TypeVarTuple

R = TypeVar("R")
Ts = TypeVarTuple("Ts")


class Memo(Generic[*Ts, R]):
    def __init__(self, fn: Callable[[*Ts], R]) -> None:
        self.fn = fn

    def __call__(self, *args: *Ts) -> R:
        return self.fn(*args)


def area(w: int, h: int) -> int:
    return w * h


print(Memo(area)(3))
