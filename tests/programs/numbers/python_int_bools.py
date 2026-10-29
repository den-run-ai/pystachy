# pystachy: python-int
# A bool stays the bool it is in a module that opts in to promoting ints: a variable, a field, a
# global or a result of a function without a return annotation that is a bool or an int holds their
# union, as in a module that does not opt in (a union holds 64-bit ints: docs/python-int.md), and a
# bool in arithmetic, comparisons, abs(), int(), float(), sum() and augmented assignment is the int
# it equals, where CPython's arithmetic promotes.
LAST = 0


def holds(c: bool, n: int) -> None:
    w = n
    if c:
        w = c
    print(w, w + 1, w == 1, type(w).__name__, repr(w), f"{w}")


def pick(c: bool, n: int):
    if c:
        return c
    return n + 1


def sign(n: int):
    if n > 0:
        return n * 2
    return n > -5


class Flag:
    def __init__(self, n: int) -> None:
        self.v = n * 3

    def clear(self, c: bool) -> None:
        self.v = c


def note(c: bool, n: int) -> None:
    global LAST
    LAST = n - 1
    if c:
        LAST = c


def arith(c: bool, n: int) -> None:
    print(n + c, c * n, -c, c + c, n - True, n ** c, n // (c + 1), n % (c + 1), c << 3, n & c, n | c, n ^ c)
    print(n == c, n < c, c >= n, c == 1, abs(c), int(c), float(c), str(c), min(c, False), max(True, c))
    x = n
    x += c
    print(x, sum([c, True, False]), sum([True], n), int(c) + n, divmod(n, c + 1), pow(c + 1, 70))


holds(True, 5)
holds(False, 7)
print(pick(True, 5), pick(False, 5), repr(pick(True, 0)), sign(3), sign(-1), sign(-9))
f = Flag(2)
print(f.v, end=" ")
f.clear(False)
print(f.v)
note(True, 4)
print(LAST, end=" ")
note(False, 4)
print(LAST)
arith(True, 5)
arith(False, 2 ** 70)
arith(True, -2 ** 64)
