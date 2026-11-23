# pystachy: dynamic-any
# divmod() of Any values: the numbers' own quotient and remainder, a's __divmod__, else b's
# __rdivmod__ (a subclass's first), and CPython's errors, once both arguments are evaluated.
from typing import Any


class Money:
    def __init__(self, cents: int) -> None:
        self.cents = cents

    def __divmod__(self, other: Any) -> Any:
        print("Money.__divmod__")
        return (self.cents // other, self.cents % other)

    def __rdivmod__(self, other: Any) -> Any:
        print("Money.__rdivmod__")
        return ("r", type(other).__name__)


class Euro(Money):
    def __rdivmod__(self, other: Any) -> Any:
        print("Euro.__rdivmod__")
        return ("euro", type(other).__name__)


class Plain:
    pass


def arg(label: str, value: Any) -> Any:
    print("argument", label)
    return value


def show(a: Any, b: Any) -> None:
    try:
        print(divmod(arg("a", a), arg("b", b)))
    except (TypeError, ZeroDivisionError) as error:
        print(type(error).__name__, error)


for a, b in [(7, 2), (-7, 2), (7, -2), (True, 2), (7.5, 2), (-7.5, 2), (7, 0.5), (1, 0), (1.0, 0), (1, 0.0), (True, False)]:
    show(a, b)
show("a", 1)
show(None, 1)
show(1, None)
show([1], 2)
show(Money(250), 100)
show(7, Money(1))
show(Money(5), Euro(2))
show(Plain(), 3)
show(3, Plain())

q, r = divmod(arg("x", 17), 5)
print(q, r, type(q).__name__)
x: Any = 2.5
print(divmod(10, x), divmod(x, 1))
big: Any = 9223372036854775807
print(divmod(big, 2))
