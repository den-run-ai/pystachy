# A tuple display of literals is the constant that CPython's compiler makes of it: each run of
# the display is that one object, and a display of the same items elsewhere in the module is the
# same object too (the compiler merges equal constants, telling 1 from True and 1.0, and 0.0
# from -0.0). A display of anything else, and a tuple that the program builds (*args, tuple(),
# a method's result), is a new tuple each time it runs (#1016).
import sys


def zero() -> tuple[float, float, float]:
    return (0.0, 0.0, 0.0)


def zero_again() -> tuple[float, float, float]:
    return (0.0, 0.0, 0.0)


def ray(x: float) -> tuple[float, float, float]:
    return (x, 0.0, 0.0)


def negative() -> tuple[float, float, float]:
    return (-0.0, 0.0, 0.0)


def empty() -> tuple[()]:
    return ()


def nested() -> tuple[tuple[int, int], tuple[int, int]]:
    return ((1, 2), (1, 2))


def mixed() -> tuple[int, bool, None, str, float]:
    return (-1, True, None, "x", 2.5)


def pair() -> tuple[int, int]:
    return 1, 2


def flags() -> tuple[bool, bool]:
    return (True, True)


def ones() -> tuple[int, int]:
    return (1, 1)


def unpacked() -> tuple[int, int]:
    return (3, 4)


def either(fresh: int) -> tuple[int, int]:
    # some returns a constant, some a new tuple: the calls that unpack take its slots by value
    if fresh > 0:
        return (fresh, fresh + 1)
    return (0, 0)


def varargs(*args: int) -> tuple[int, ...]:
    return args


def text(s: str) -> tuple[str, str, str]:
    return s.partition(",")


print(zero() is zero(), zero() is zero_again(), ray(0.0) is ray(0.0))
print(zero() is negative(), negative() is negative(), negative(), zero() == negative())
print(empty() is empty(), len(empty()))
n = nested()
print(n[0] is n[1], n is nested(), n)
print(mixed() is mixed(), mixed())
print(pair() is pair(), pair())
print(flags() is flags(), ones() is ones(), flags() == ones())
a, b = unpacked()
print(a, b, unpacked() is unpacked())
x, y = either(0)
p, q = either(5)
print(x, y, p, q, either(0) is either(0), either(5) is either(5), either(0) is either(-1))
made = [zero() for _ in range(3)]
print(made[0] is made[1], made[1] is made[2], made)
print(varargs(1, 2) is varargs(1, 2), varargs(1, 2) == varargs(1, 2))
print(text("a,b") is text("a,b"), text("a,b"))
print(tuple(v for v in (1, 2)) is tuple(v for v in (1, 2)))
d: dict[tuple[int, int], str] = {}
d[pair()] = "pair"
d[(1, 2)] = "again"
print(len(d), d[1, 2], (1, 2) in d, d)
s = set([pair(), (1, 2), unpacked()])
print(len(s), sorted(s))
held = [zero(), ray(1.0)]
kept = [nested(), nested()]
for _ in range(2000):
    held.append(ray(float(len(held))))
    kept.append(((len(kept), 0), (0, 0)))
print(held[0] is zero(), held[1] is ray(1.0), kept[0][1] is nested()[0], kept[-1][1] is kept[2][1])
print(held[0], held[-1], kept[1], kept[-1], len(held), len(kept))
sys.stdout.flush()
