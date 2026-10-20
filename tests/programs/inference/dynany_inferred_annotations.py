# pystachy: dynamic-any
# In a module that compiles typing.Any as dynamic values, an annotation that mentions Any where no
# Any value can stand requests inference, as it does in modules that do not opt in (#782):
# Callable[..., Any], whose parameters no Callable type names, and a generic class's type
# argument, which its constructor's call gives.
from collections.abc import Callable
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value


def apply(fn: Callable[..., Any], *args: Any) -> Any:
    return fn(*args)


def twice(fn: Callable[..., Any], x: int) -> Any:
    return fn(fn(x))


def add(a: int, b: int) -> int:
    return a + b


def shout(s: str) -> str:
    return s.upper() + "!"


box: Box[Any] = Box(3)
print(apply(add, 2, 3), apply(shout, "hi"), twice(lambda x: x * 10, 2), box.value)
