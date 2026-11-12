# number op object calls the object's reflected method (__radd__, __rsub__, ...): a builtin number
# has no method for it. The operands are evaluated left to right before the call, the method is
# dispatched on the object's class, and a None object raises CPython's TypeError.


class Money:
    def __init__(self, cents: int) -> None:
        self.cents = cents

    def __add__(self, other: int) -> "Money":
        print("Money.__add__", other)
        return Money(self.cents + other * 100)

    def __radd__(self, other: int) -> "Money":
        print("Money.__radd__", other)
        return Money(self.cents + other * 100)

    def __rsub__(self, other: int) -> "Money":
        return Money(other * 100 - self.cents)

    def __rmul__(self, other: int) -> "Money":
        return Money(self.cents * other)

    def __rtruediv__(self, other: float) -> float:
        return other / (self.cents / 100)

    def __rfloordiv__(self, other: int) -> int:
        return other * 100 // self.cents

    def __rmod__(self, other: int) -> int:
        return other * 100 % self.cents

    def __rand__(self, other: int) -> int:
        return other & self.cents

    def __ror__(self, other: int) -> int:
        return other | self.cents

    def __rxor__(self, other: int) -> int:
        return other ^ self.cents

    def __rlshift__(self, other: int) -> int:
        return other << (self.cents % 8)

    def __rrshift__(self, other: int) -> int:
        return other >> (self.cents % 8)

    def __repr__(self) -> str:
        return "Money(%d)" % self.cents


class Loud(Money):
    def __radd__(self, other: int) -> "Money":
        print("Loud.__radd__", other)
        return Money(-1)


class Ratio:
    def __init__(self, value: float) -> None:
        self.value = value

    def __radd__(self, other: float) -> float:
        return other + self.value

    def __rmul__(self, other: int | float) -> float:
        return other * self.value


def left() -> int:
    print("left")
    return 2


def right(m: Money) -> Money:
    print("right")
    return m


def show(m: Money) -> None:
    print(1 + m, 10 - m, 3 * m, 2.5 / m, 7 // m, 7 % m, m + 1)
    print(6 & m, 8 | m, 5 ^ m, 1 << m, 1024 >> m)


show(Money(250))
show(Loud(250))
print(left() + right(Money(5)))
print(1.5 + Ratio(0.25), 2 * Ratio(1.5), 2.0 * Ratio(1.5), [n * Money(3) for n in range(3)])
total = 0 + Money(1)
total = 2 + total
print(total)


def none_case(n: int) -> None:
    m: Money | None = Money(1) if n == 0 else None
    try:
        print(1 + m)
    except TypeError as error:
        print("TypeError:", error)


none_case(0)
none_case(1)
