# pystachy: python-int
# A tuple display of int literals in a module whose ints promote is CPython's constant too (#1016):
# its promoting int items are held as the 64-bit literals they are, so a display that an annotated
# return makes promoting is the same object at each run, and the same as an equal display of
# 64-bit ints. A display with -2**63 (whose slot would say to read an Mpz word) or an int past 64
# bits is made at each run, which this program shows only by its values.
def origin() -> tuple[int, int]:
    return (0, 0)


def again() -> tuple[int, int]:
    return (0, 0)


def nested() -> tuple[tuple[int, int], str]:
    return ((1, -2), "x")


def edge() -> tuple[int, int]:
    return (-9223372036854775808, 1)


def big() -> tuple[int, int]:
    return (18446744073709551616, 1)


def either(n: int) -> tuple[int, int]:
    # (some returns a constant, some a new tuple: an unpacking takes the slots by value)
    if n > 0:
        return (n, n * 2)
    return (0, 0)


plain = (0, 0)
x, y = origin()
print(origin() is origin(), origin() is again(), origin() is plain, x, y)
print(nested() is nested(), nested()[0] is nested()[0], nested())
a, b = either(0)
c, d = either(3)
print(a, b, c, d, either(0) is origin(), either(0) is either(-1), either(4) is either(4))
print(edge(), edge() == edge(), edge()[0] - 1, big(), big() == big(), big()[0] + 1)
print(sum(origin()), [t for t in again()], hash(origin()) == hash((0, 0)))
