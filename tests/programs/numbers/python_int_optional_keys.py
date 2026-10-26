# pystachy: python-int
# An int | None of a module that opts in to promoting ints (docs/python-int.md) where 64-bit storage
# takes it: a dict's key (subscripts, augmented assignment, del), a default of pop(), a set's
# element (discard(), remove()) and the errno of an OSError, which names its class (also of a
# promoting int); one past 64 bits is in no range, and a SystemExit's status is its value, -1 past
# 64 bits.


def code(v: int) -> int | None:
    return v if v > 0 else None


class Quit(SystemExit):
    pass


def keyed(v: int) -> None:
    y = code(v)
    d = {5: 50, 7: 70}
    try:
        print(d[y], end=" ")
        d[y] += 1
        print(d[y], end=" ")
        del d[y]
        print(d)
    except KeyError as e:
        print("KeyError", e)
    print(d.pop(9, y), d.pop(7, y))
    s = {5, 6}
    s.discard(y)
    try:
        s.remove(y)
    except KeyError as e:
        print("KeyError", e, end=" ")
    print(s)


def ranged(v: int) -> None:
    y = code(v)
    r = range(0, 100, 5)
    print(y in range(10), y in range(0, 10, 5), y in r, y not in r)


def errno(v: int) -> None:
    try:
        raise OSError(code(v), "x")
    except OSError as e:
        print(type(e).__name__, e)


for v in (5, 7, 6, -1):
    keyed(v)
for v in (5, 7, 2 ** 70, -1):
    ranged(v)
for v in (2, 13, 2 ** 70, -1):
    errno(v)
for n in (2, 2 ** 70):
    try:
        raise OSError(n, "y")
    except OSError as e:
        print(type(e).__name__, e)
try:
    raise SystemExit(code(5))
except SystemExit as e:
    print("SystemExit", e, repr(e))
try:
    raise Quit(code(-1))
except SystemExit as e:
    print("Quit", repr(e))
raise Quit(code(2 ** 70))
