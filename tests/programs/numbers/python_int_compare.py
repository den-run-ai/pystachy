# pystachy: python-int
# Promoting ints (docs/python-int.md): comparisons with ints past 64 bits, with 64-bit ints, bools
# and floats (exact, as CPython compares an int with a float), in chains and conditions.

from collections.abc import Iterator
from typing import NamedTuple

MAX = 9223372036854775807
MIN = -9223372036854775808


def value(i: int) -> int:
    if i == 0:
        return MIN - 1
    if i == 1:
        return MIN
    if i == 2:
        return -1
    if i == 3:
        return 0
    if i == 4:
        return 1
    if i == 5:
        return MAX
    if i == 6:
        return MAX + 1
    if i == 7:
        return 2 ** 64
    return -(2 ** 100)


def flt(i: int) -> float:
    if i == 0:
        return 9.223372036854775808e18
    if i == 1:
        return -9.223372036854775808e18
    if i == 2:
        return 2.0 ** 64
    if i == 3:
        return 0.5
    if i == 4:
        return -0.5
    if i == 5:
        return float("inf")
    if i == 6:
        return float("-inf")
    if i == 7:
        return float("nan")
    return -(2.0 ** 100)


for i in range(9):
    a = value(i)
    print(a, " ".join([str((a < value(j), a <= value(j), a == value(j), a != value(j), a > value(j), a >= value(j))) for j in range(9)]))
for i in range(9):
    a = value(i)
    print(a, " ".join([str((a < flt(j), a == flt(j), a != flt(j), flt(j) < a, flt(j) >= a)) for j in range(9)]))

x = 2 ** 70
print(MIN - 1 < MIN < 0 < MAX < MAX + 1 < x, x > MAX > 0, 0 < x < MAX, x == x + 0, x != x - 1)
print(x == 2 ** 70, -x == -(2 ** 70), x == 1180591620717411303424.0, x + 1 == 1180591620717411303424.0)
print(x > True, True < x, (x - x) == False, x * 0 == 0, 2 ** 53 + 1 == 9007199254740992.0, 2 ** 53 + 1 > 9007199254740992.0)
print(x == None, x != None, x is None, x is not None, not x, not (x - x), bool(x), bool(x - x))
n = 0
if x:
    n += 1
if -x:
    n += 2
if x - x:
    n += 4
while x > MAX:
    x //= 3
    n += 1
print(n, x)
print(max(2 ** 70, 3, -5), min(2 ** 70, 3, -5), max(-(2 ** 70), MIN), min(MAX + 1, MAX), abs(MIN), abs(-(2 ** 70)))

# a promoting int is an int; never equal to a str, bytes or container; and/or keep either operand
big = 2 ** 70
zero = big - big


def kind(v: int) -> str:
    if isinstance(v, int):
        return "int " + str(v)
    return "other"


print(isinstance(big, int), isinstance(big, float), isinstance(big, (str, int)), isinstance(-big, bool), kind(big))
print(big == "x", big != "x", big == [1], big != (1,), "" == big, big == {1: 2}, big != {1})
print(zero or big, big or zero, zero and big, big and zero, 3 and big, zero or -big)
print(big in [0, 1], zero in [0, 1], big in (1, 2), big - 1 not in {1, 2}, big in range(5), zero in range(5), big in {0: 1})
print((2 ** 40).bit_length(), (big // big).bit_length(), (2 ** 62 + 2 ** 62 - 1).bit_count(), (-big // big).bit_length())
r = range(0, 2 ** 62, 3)
print(big in r, big - big in r, 2 ** 61 + 2 in r, big in range(-1, 1), -big not in r)


# membership in an iterator object whose __next__ returns promoting ints compares them as ints
class Count:
    def __init__(self, n: int) -> None:
        self.n = n
        self.i = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.i >= self.n:
            raise StopIteration
        self.i += 1
        return self.i - 1


print(2 in Count(3), 4 in Count(3), 0 not in Count(1), zero in Count(1), True in Count(2), 1.0 in Count(2))


# x in o of an object takes x as it is: its __contains__ as the parameter does, an iterator's or a
# generator's items compared exactly, also past 64 bits
class Evens:
    def __contains__(self, x: int) -> bool:
        return x % 2 == 0


class Odds(Evens):
    def __contains__(self, x: int) -> bool:
        return x % 2 == 1


class Box:
    def __iter__(self):
        return iter([1, 2, 3])


def pick(odd: bool) -> Evens:
    if odd:
        return Odds()
    return Evens()


def upto(n: int):
    for i in range(n):
        yield i


class Pair(NamedTuple):
    x: int
    y: int


class Floats:
    def __iter__(self) -> Iterator[float]:
        return iter([1.0, 2.0])


class Flags:
    def __iter__(self) -> Iterator[bool]:
        return iter([True, False])


class Ints:
    def __iter__(self) -> Iterator[int]:
        return iter([1, 2])


c = Count(5)
print(big in Count(3), -big not in Count(3), big in Evens(), big + 1 in Evens(), big in pick(True), big + 1 in pick(True))
print(big in Box(), 2 in Box(), big in upto(3), 2 in upto(3), big in c, next(c, -1))
print(big in Pair(1, big), big + 1 in Pair(1, big), big in Pair(3, 4), 4 in Pair(3, 4))
one = big // big
print(one in Floats(), zero in Floats(), zero in Flags(), one not in Flags(), big in Ints(), one in Ints())
