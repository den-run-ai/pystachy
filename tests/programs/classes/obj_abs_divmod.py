# abs(o) calls o.__abs__() and divmod(o, x) calls o.__divmod__(x), dispatched on the object's
# class; both arguments are evaluated first, and None raises CPython's TypeError.


class Money:
    def __init__(self, cents: int) -> None:
        self.cents = cents

    def __abs__(self) -> "Money":
        print("Money.__abs__", self.cents)
        return Money(abs(self.cents))

    def __divmod__(self, parts: int) -> tuple["Money", "Money"]:
        q, r = divmod(self.cents, parts)
        return Money(q), Money(r)

    def __repr__(self) -> str:
        return "Money(%d)" % self.cents


class Debt(Money):
    def __abs__(self) -> "Money":
        print("Debt.__abs__")
        return Money(-self.cents)


def arg(tag: str, n: int) -> int:
    print("arg", tag)
    return n


def first(m: Money) -> Money:
    print("first")
    return m


for m in [Money(-250), Debt(75), Money(0)]:
    print(abs(m), divmod(first(m), arg("parts", 3)))

missing: Money | None = None
if arg("cond", 0):
    missing = Money(1)
try:
    print(abs(missing))
except TypeError as e:
    print("TypeError:", e)
try:
    print(divmod(missing, arg("x", 4)))
except TypeError as e:
    print("TypeError:", e)
