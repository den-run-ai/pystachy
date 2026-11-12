# An IntEnum or IntFlag member where CPython asks for an index: a subscript, a slice bound,
# range(), a repetition count, hex(), oct(), bin() and the integer conversions of % formatting
# use its value. Its ** and bit_length() are int's.
from enum import Enum, IntEnum, IntFlag


class Color(IntEnum):
    RED = 1
    GREEN = 2


class Perm(IntFlag):
    R = 4
    W = 2


class Level(int, Enum):
    LOW = 0
    HIGH = 3


c = Color.GREEN
p = Perm.R
xs = [10, 20, 30, 40, 50]
print(xs[c], xs[Color.RED], xs[:c], xs[c:], xs[c:p], "abcdef"[c], "abcdef"[c:p], xs[Level.HIGH], xs[Level.LOW:Level.HIGH])
print(list(range(c)), list(range(c, 5)), range(c, p), [i for i in range(Color.RED, p)], range(Level.HIGH))
print("ab" * c, [0] * c, c * "x", c * [1], p * "-", b"a" * c, Level.HIGH * "ab")
print(hex(c), bin(p), oct(c), hex(Level.HIGH))
print("%d %x %o %c %5d %s %r %.2f" % (c, p, c, c + 64, p, c, c, c))
xs[c] = 0
xs[Color.RED] += 1
del xs[p]
print(xs)
print(c ** 2, pow(c, 3), c ** 0.5, c.bit_length(), Level.HIGH ** 2, Level.HIGH.bit_length())
for i in range(Color.GREEN):
    print(i)
print(c * 1.5, c * 3, p * 2)
