# pystachy: dynamic-any
# Making an object of a class with abstract methods where the object is boxed as Any, as an Any
# parameter's argument or an Any variable's value, raises CPython's TypeError (#1618)
from abc import ABC, abstractmethod
from typing import Any


class Half(ABC):
    @abstractmethod
    def f(self) -> int:
        return 0


class Full(Half):
    def f(self) -> int:
        return 1


def show(x: Any) -> None:
    print(type(x).__name__)


try:
    show(Half())
except TypeError as e:
    print("argument", e)
try:
    x: Any = Half()
    print(x)
except TypeError as e:
    print("variable", e)
show(Full())
y: Any = Full()
print(y.f())
