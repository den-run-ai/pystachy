# error: Holder() cannot bind its type variables from the argument for 'make', a <function <lambda> (tests/errors/generics/generic_callable_unbound.py:13)>: the lambda has no return annotation, which the type variable it matches takes its type from
# A lambda's result types a Callable only where the context or another argument binds it
from typing import Callable, Generic, TypeVar

V = TypeVar("V")


class Holder(Generic[V]):
    def __init__(self, make: Callable[[], V]) -> None:
        self.make: Callable[[], V] = make


h = Holder(lambda: 0)
print(h.make())
