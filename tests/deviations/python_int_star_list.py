# pystachy: python-int
# Documented deviation (docs/python-int.md#64-bit-boundaries): f(*xs) of a list known only at run
# time makes the *args it fills a tuple[int, ...], which holds 64-bit ints as tuple(xs) does, so an
# item past 64 bits that goes into *args raises OverflowError, where CPython goes on with the
# bigger int. Items that fill the parameters before *args keep it, and so does *args of the
# call's own arguments.
def total(*args: int) -> int:
    r = 0
    for a in args:
        r += a
    return r


def first(a: int, *rest: int) -> int:
    return a + len(rest)


xs = [1, 2 ** 70, 3]
print(first(*xs[1:]), total(1, 2 ** 70))
try:
    print(total(*xs))
except OverflowError as e:
    print("OverflowError", e)
