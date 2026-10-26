# pystachy: python-int
# Promoting ints (docs/python-int.md) across functions, methods, fields, globals, closures and
# module boundaries. A module that does not opt in keeps 64-bit ints: values that fit pass into
# it, and a promoting int it receives keeps promoting.
from fixed_width import first_digit, scale
from promoting import LIMIT, grow, total

BASE = 10 ** 18


def power(b: int, e: int = 64) -> int:
    r = 1
    while e > 0:
        if e & 1:
            r *= b
        b *= b
        e >>= 1
    return r


def ackermann_ish(n):
    # (no annotations: the result's type comes from the values)
    if n == 0:
        return 1
    return ackermann_ish(n - 1) * BASE + n


grand = 0


def add_grand(k: int) -> None:
    global grand
    grand += k * BASE * BASE


class Ledger:
    def __init__(self, opening: int) -> None:
        self.balance = opening
        self.history = 0

    def deposit(self, amount: int, times: int = 1) -> int:
        self.balance += amount * times
        self.history += 1
        return self.balance


def counter(step: int):
    value = 0

    def bump() -> int:
        nonlocal value
        value += step
        return value
    return bump


print(power(2), power(3, 41), power(b=10, e=20), power(-7, 25))
print(ackermann_ish(3), ackermann_ish(1))
book = Ledger(BASE * BASE)
book.deposit(BASE, times=10 ** 6)
print(book.deposit(-BASE * BASE), book.history, book.balance > BASE)
c = counter(2 ** 62)
c()
c()
print(c(), c() - 2 ** 64)
square = lambda v: v * v
print(square(BASE), square(-BASE * 10))
print(scale(BASE, 9), first_digit(power(2, 62)), first_digit(2 ** 63 - 1))
print(grow(BASE), total(4), LIMIT - 1, grow(LIMIT) // LIMIT == LIMIT)
add_grand(1)
add_grand(-3)
print(grand, grand // BASE)
