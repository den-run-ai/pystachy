# unary - + ~ on an object (a name, a field, an item, a call's result, another unary operator's)
# call __neg__, __pos__ and __invert__ of its class (or of an exception class's base) once the
# operand is evaluated, and give what the method returns: an object of any class, an int, a str;
# an object that is None raises CPython's TypeError
import operator
from dataclasses import dataclass
from typing import NamedTuple


class Bits:
    def __init__(self, n: int) -> None:
        self.n = n

    def __invert__(self) -> "Bits":
        return Bits(~self.n & 15)

    def __repr__(self) -> str:
        return f"Bits({self.n:04b})"


class Vec:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def __neg__(self) -> "Vec":
        return Vec([-x for x in self.xs])

    def __pos__(self) -> str:
        return f"+{self.xs}"

    def __repr__(self) -> str:
        return f"Vec({self.xs})"


a = Bits(0b1100)
v = Vec([1, 2, 3])
print(~a, ~~a, (-v).xs, +v, +-v, -(-v), -v is v)


class Num:
    def __init__(self, k: int) -> None:
        self.k = k

    def __neg__(self) -> "Num":
        print("neg", self.k)
        return Num(-self.k)

    def __pos__(self) -> "Num":
        print("pos", self.k)
        return self

    def __invert__(self) -> "Num":
        print("invert", self.k)
        return Num(~self.k)

    def __repr__(self) -> str:
        return f"Num({self.k})"


def num(k: int) -> Num:
    print("operand", k)
    return Num(k)


o = Num(5)
print(-~+o, +o is o)  # +o first, then ~, then -
print(-num(1), ~num(2))  # each operand, then its method


class Box:
    def __init__(self, n: Num) -> None:
        self.n = n
        self.m: Num = -n

    def flip(self) -> Num:
        return ~self.n


bx = Box(Num(3))
print(-bx.n, bx.m, bx.flip())
ns = [Num(1), Num(2)]
d = {"a": Bits(1)}
t = (Num(7), Bits(2))
print(-ns[1], ~d["a"], +t[0], ~t[1], [-x for x in ns])


class Neg:
    def __init__(self, x: int) -> None:
        self.x = x

    def __neg__(self) -> int:
        return -self.x


class Holder:
    def __init__(self, v: Neg) -> None:
        self.n: int = -v


print(Holder(Neg(3)).n, -Neg(4) + 1, -(-Neg(5)), max([-q for q in [Neg(2), Neg(9), Neg(4)]]))


class Debt:
    def __init__(self, owed: int) -> None:
        self.owed = owed

    def __neg__(self) -> "Money":
        return Money(self.owed)


class Money:
    def __init__(self, cents: int) -> None:
        self.cents = cents

    def __neg__(self) -> Debt:
        return Debt(self.cents)

    def __repr__(self) -> str:
        return f"Money({self.cents})"


m = Money(250)
print((-m).owed, -(-m), isinstance(-m, Debt), isinstance(-m, Money))


@dataclass
class Mask:
    bits: int

    def __invert__(self) -> "Mask":
        return Mask(~self.bits & 0xFF)


class Flags(NamedTuple):
    r: bool
    w: bool

    def __invert__(self) -> "Flags":
        return Flags(not self.r, not self.w)


print(~Mask(0b1010), ~~Mask(3) == Mask(3), ~Flags(True, False), ~Flags(True, False) == (False, True))


class Shift(Exception):
    def __init__(self, k: int) -> None:
        super().__init__(k)
        self.k = k

    def __neg__(self) -> int:
        return -self.k * 10

    def __invert__(self) -> "Shift":
        return Shift(~self.k)


class Up(Shift):
    def __init__(self, k: int) -> None:
        super().__init__(k + 1)


class UpUp(Up):
    pass


print(-Up(1), -UpUp(2), (~Up(3)).k, type(~UpUp(4)).__name__)
try:
    raise UpUp(5)
except Shift as e:
    print(-e, ~e)


def negate(x):
    return -x


print(negate(v), negate(Neg(6)), negate(7), negate(2.5))
print(operator.neg(o), operator.pos(v), operator.inv(a), operator.invert(Mask(1)))


def pick(k: int) -> Num | None:
    return Num(k) if k > 0 else None


class Slot:
    def __init__(self) -> None:
        self.n: Num | None = None


print(-pick(2))
for k in [3, 0]:
    p = pick(k)
    if p is not None:
        print(~p)
    for op in "-+~":
        try:
            print(-p if op == "-" else +p if op == "+" else ~p)
        except TypeError as e:
            print("TypeError:", e)
try:
    print(-Slot().n)
except TypeError as e:
    print("TypeError:", e)
try:
    print(~d.get("z"))
except TypeError as e:
    print("TypeError:", e)


class Bad:
    def __neg__(self) -> int:
        raise ValueError("no negative")


try:
    print(-Bad())
except ValueError as e:
    print("ValueError:", e)
print(-True, +False, -2.5, +3, ~7, -(-9), +-+1.5)
