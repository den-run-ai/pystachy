# int(o) calls o.__int__(), else o.__index__(); float(o) calls o.__float__(), else o.__index__();
# round(o) and round(o, n) call o.__round__, a template whose result each call types; math.floor(o),
# math.ceil(o) and math.trunc(o) call o.__floor__(), o.__ceil__() and o.__trunc__(). The calls
# dispatch on the object's class, evaluate their arguments first, and None raises CPython's TypeError.
import math


class Money:
    def __init__(self, cents: int) -> None:
        self.cents = cents

    def __int__(self) -> int:
        print("Money.__int__")
        return self.cents // 100

    def __float__(self) -> float:
        return self.cents / 100

    def __round__(self, ndigits=None):
        if ndigits is None:
            return (self.cents + 50) // 100
        return Money(self.cents - self.cents % 10 ** (2 - ndigits))

    def __floor__(self) -> int:
        return self.cents // 100

    def __ceil__(self) -> int:
        return -(-self.cents // 100)

    def __trunc__(self) -> int:
        return int(self.cents / 100)

    def __repr__(self) -> str:
        return "Money(%d)" % self.cents


class Debt(Money):
    def __int__(self) -> int:
        print("Debt.__int__")
        return -(self.cents // 100)

    def __float__(self) -> float:
        return -1.5


class Slot:
    def __index__(self) -> int:
        return 7


class Fixed:
    def __round__(self, ndigits: int = 0) -> int:
        return 40 + ndigits


def show(m: Money) -> None:
    print(int(m), float(m), round(m), round(m, 1), round(m, None), math.floor(m), math.ceil(m), math.trunc(m))


def arg(tag: str, m: Money) -> Money:
    print("arg", tag)
    return m


show(Money(1234))
show(Money(-1234))
show(Debt(1234))
print(int(Slot()), float(Slot()), round(Fixed()), round(Fixed(), 2), round(Fixed(), None))
print(int(arg("a", Money(250))) + int(arg("b", Debt(250))), [int(m) for m in [Money(100), Debt(250)]], [float(m) for m in [Money(100), Debt(250)]])
print(type(int(Money(5))).__name__, type(float(Money(5))).__name__, type(round(Money(5))).__name__, type(round(Money(5), 1)).__name__)


def none_case(which: int, n: int) -> None:
    m: Money | None = Money(199) if n == 0 else None
    try:
        if which == 0:
            print(int(m))
        elif which == 1:
            print(float(m))
        elif which == 2:
            print(round(m))
        elif which == 3:
            print(math.floor(m))
        elif which == 4:
            print(math.trunc(m))
    except TypeError as error:
        print("TypeError:", error)


for which in range(5):
    none_case(which, 0)
    none_case(which, 1)
