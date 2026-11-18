# An object where CPython asks for an index gives its class's __index__(): a subscript, a
# slice bound, a repetition count, range() and the integer conversions of % formatting. The
# operands are evaluated first, a slice asks its step before its bounds, and o[k] op= v asks
# k twice, as CPython's read and store do.
class I:
    def __init__(self, n: int) -> None:
        self.n = n

    def __index__(self) -> int:
        print("index", self.n)
        return self.n


class Twice(I):
    def __index__(self) -> int:
        print("twice", self.n)
        return self.n * 2


class J:
    def __int__(self) -> int:
        return 7

    def __index__(self) -> int:
        return 9


class F:
    def __float__(self) -> float:
        return 2.5


def mk(n: int) -> I:
    print("mk", n)
    return I(n)


xs = [10, 20, 30, 40, 50]
print(xs[I(2)], "abcde"[I(1)], b"abc"[I(2)], xs[I(-1)])
print(xs[mk(1):mk(4)], xs[mk(4):mk(0):mk(-2)], "abcdef"[:I(3)], xs[I(3):], b"abcdef"[I(1):I(3)])
xs[I(0)] = 11
xs[I(1)] += 5
del xs[I(4)]
print(xs)
xs[I(1):I(2)] = [1, 2]
del xs[I(0):I(1)]
print(xs)
print(list(range(I(3))), list(range(mk(1), mk(7), mk(2))), range(I(2)), [i for i in range(I(2))])
print("ab" * I(2), [0] * I(3), I(2) * "xy", I(2) * [1], b"z" * I(2))
print("%d %x %o %X %5d|%-4d|%c %.1f %e" % (I(10), I(255), I(8), I(255), I(7), I(3), I(65), I(2), I(1)))
print("%d %x %i %.2f %g" % (J(), J(), J(), F(), F()))
items: list[I] = [I(1), Twice(1)]
for it in items:
    print(xs[it], "x" * it, "%d" % it, list(range(it)))
try:
    print(xs[I(100)])
except IndexError as e:
    print("IndexError:", e)


def none_cases(which: int) -> None:
    o: I = I(1) if which < 0 else None
    ys: list[int] | None = None if which == 5 else [1, 2, 3]
    try:
        if which == 0:
            print(xs[o])
        elif which == 1:
            print(xs[o:], xs[:o], xs[::o])
        elif which == 2:
            print("ab" * o)
        elif which == 3:
            print(list(range(o)))
        elif which == 4:
            print("%d" % o)
        elif which == 5:
            print(ys[mk(0)])
    except TypeError as e:
        print("TypeError:", e)


for w in range(6):
    none_cases(w)
