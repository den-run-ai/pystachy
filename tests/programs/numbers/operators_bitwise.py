# & | ^ << >> @ call their methods, unary - + ~ __neg__, __pos__ and __invert__, and the in-place
# forms __iand__ & co, else the binary method
import operator
from typing import NamedTuple


class Bits:
    def __init__(self, n: int) -> None:
        self.n = n

    def __and__(self, o: "Bits") -> "Bits":
        print("and", self.n, o.n)
        return Bits(self.n & o.n)

    def __or__(self, o: "Bits") -> "Bits":
        return Bits(self.n | o.n)

    def __xor__(self, o: "Bits") -> "Bits":
        return Bits(self.n ^ o.n)

    def __lshift__(self, k: int) -> "Bits":
        return Bits(self.n << k)

    def __rshift__(self, k: int) -> "Bits":
        return Bits(self.n >> k)

    def __invert__(self) -> "Bits":
        return Bits(~self.n & 15)

    def __ior__(self, o: "Bits") -> "Bits":
        self.n |= o.n
        return self

    def __ixor__(self, o: "Bits") -> "Bits":
        return Bits(self.n ^ o.n ^ 1)  # (what it returns is bound, as CPython does)

    def __repr__(self) -> str:
        return f"Bits({self.n:04b})"


def bits(k: int) -> Bits:
    print("operand", k)
    return Bits(k)


a = Bits(0b1100)
b = Bits(0b1010)
print(a | b, a ^ b, a << 2, a >> 1, ~a)
print(a | b & a ^ b, ~(a | b) | a)  # & binds tighter than ^, ^ than |
print(bits(1) & bits(3))  # both operands first, then the method
c = a
c |= b  # __ior__ changes c in place
print(c, a, c is a)
c &= Bits(0b1001)  # no __iand__: __and__ makes another object
print(c, a, c is a)
c ^= b
c <<= 2
c >>= 1
print(c, a)


def either(x, y):
    return x | y


print(either(a, b), either(6, 3), operator.and_(a, b), operator.inv(a))
for k in [-1, 2]:
    try:
        print(b >> k)
    except ValueError as e:
        print("ValueError:", e)


class Vec:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def __matmul__(self, o: "Vec") -> int:
        return sum([x * y for x, y in zip(self.xs, o.xs)])

    def __imatmul__(self, k: int) -> "Vec":
        self.xs = [x * k for x in self.xs]
        return self

    def __neg__(self) -> "Vec":
        return Vec([-x for x in self.xs])

    def __pos__(self) -> str:
        return f"+{self.xs}"


v = Vec([1, 2, 3])
print(v @ Vec([4, 5, 6]), (-v).xs, +v, -(-v) @ v)
v @= 10
print(v.xs, +-v)


class Neg:
    def __init__(self, x: int) -> None:
        self.x = x

    def __neg__(self) -> int:
        return -self.x


class Holder:
    def __init__(self, v: Neg) -> None:
        self.n: int = -v


print(Holder(Neg(3)).n, -Neg(4) + 1)


class Flags(NamedTuple):
    r: bool
    w: bool

    def __or__(self, o: "Flags") -> "Flags":
        return Flags(self.r or o.r, self.w or o.w)

    def __invert__(self) -> "Flags":
        return Flags(not self.r, not self.w)


f = Flags(True, False) | Flags(False, False)
print(f, ~f, f | ~f)


class Mask(NamedTuple):
    bits: int

    def __or__(self, o: tuple[int]) -> int:
        return self.bits | o[0]

    def __and__(self, o: Flags) -> str:
        return f"{self.bits} {o.r}"

    def __xor__(self, o):
        return self.bits ^ o[0]


# a NamedTuple's own method runs first, also with a tuple or another NamedTuple operand
print(Mask(1) | (2,), Mask(3) & f, Mask(5) ^ (1,), Mask(5) ^ Mask(4), Mask(5) ^ [7])


class Base(Exception):
    def __or__(self, o: "Base") -> str:
        return "Base.__or__"

    def __ror__(self, o: "Base") -> str:
        return "Base.__ror__"


class Derived(Base):
    pass


# Derived's __ror__ is Base's, so CPython calls the left operand's __or__ first either way
print(Base() | Derived(), Derived() | Base())


def maybe(k: int) -> Bits | None:
    return Bits(k) if k > 0 else None


m = maybe(0)
try:
    print(m | b)
except TypeError as e:
    print("TypeError:", e)
try:
    print(~m)
except TypeError as e:
    print("TypeError:", e)
try:
    m ^= b
except TypeError as e:
    print("TypeError:", e)
try:
    print(b & m)  # Bits.__and__ runs with None
except AttributeError as e:
    print("AttributeError:", e)
