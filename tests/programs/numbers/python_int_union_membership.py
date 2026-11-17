# pystachy: python-int
# A tuple's in, not in, count() and index() compare a promoting int with a closed union as CPython
# compares them (#1354): the union holds a 64-bit int, so a promoting int that fits 64 bits
# compares with the int, bool or float the union holds, and one past 64 bits equals only a float
# of its value. The pair counted as values of types that are never equal: 1 in ("one", 1, 2.5)
# was False for a union holding 1, either side the union was on.


def has(key: int | str | None, t: tuple[str, int, float]) -> None:
    try:
        at = t.index(key)
    except ValueError:
        at = -1
    print(repr(key), key in t, key not in t, t.count(key), at, t[1] in (key, "z"), t[1] not in (key,), (key, t[1], key).count(t[1]), (key, t[1]).index(t[1]))


def floats(key: float | str, t: tuple[int, str]) -> None:
    print(repr(key), t[0], key in t, t.count(key), t[0] in (key,), (key, key).count(t[0]))


def bools(key: bool | str, t: tuple[int, str]) -> None:
    print(repr(key), t[0], key in t, t.count(key), t[0] in (key,))


def items(n: int, t: tuple[int | str, float | str]) -> None:
    print(n, t, n in t, n not in t, t.count(n), (t[1], t[0], n).index(n))


for key in [1, "one", None, 2, 2**62, -(2**63), 0]:
    has(key, ("one", 1, 2.5))
    has(key, ("x", 2**62, 1.0))
    has(key, ("", -(2**63), 0.0))
    has(key, ("one", 2**70, 2.5))
for t in [(1, "a"), (2**62, "a"), (2**70, "a"), (2**70 + 1, "a"), (-(2**63), "a"), (-(2**64), "a")]:
    for f in [1.0, 2.0**62, 2.0**70, -(2.0**63), -(2.0**64), float("nan"), "a"]:
        floats(f, t)
for t in [(1, "a"), (0, "a"), (2**70, "a")]:
    for b in [True, False, "a"]:
        bools(b, t)
for n in [1, 2**62, 2**70, -(2**63)]:
    items(n, (1, 1.0))
    items(n, ("a", 2.0**62))
    items(n, (2**62, 2.0**70))
    items(n, (-(2**63), "b"))
