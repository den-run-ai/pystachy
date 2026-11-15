# set[T | None]: None beside strs, ints, bytes and tuples, found by hash(None) and identity
def strs() -> None:
    s: set[str | None] = set()
    s.add("a")
    s.add(None)
    s.add("b")
    s.add(None)
    print(len(s), None in s, "a" in s, "z" in s, None not in s)
    k: str | None = None
    print(k in s, k not in s)
    k = "b"
    print(k in s)
    k = "q"
    print(k in s)
    s.discard(None)
    print(len(s), None in s)
    s.discard(None)
    try:
        s.remove(None)
    except KeyError as e:
        print("KeyError", e)
    s.add(None)
    s.remove(None)
    s.add(None)
    print(sorted([x for x in s if x is not None]), len([x for x in s if x is None]))
    t = {None, "a", "c"}
    print(len(t), None in t, sorted([x for x in t if x is not None]))
    print(len(s | t), len(s & t), len(s - t), len(s ^ t), None in (s & t), None in (s - t), None in (s ^ t))
    print(s == t, s <= t, s.isdisjoint(t), (s & t) <= s, s == s.copy())
    s -= {None}
    print(None in s, len(s))
    s |= {None}
    print(None in s, len(s))
    s &= {None, "b"}
    print(sorted([x for x in s if x is not None]), None in s)
    s ^= {None}
    print(sorted([x for x in s if x is not None]), None in s)
    u: set[str | None] = {x for x in ["p", None, "p", None]}
    print(len(u), None in u, "p" in u)
    fs: frozenset[str | None] = frozenset([None, "a"])
    print(len(fs), None in fs, "a" in fs, fs == {"a", None})
    e: set[str | None] = set()
    print(len(e), None in e, e == set(), bool(e))
    e.update(["m", None])
    e.update({"n"})
    print(len(e), None in e)
    only: set[str | None] = {None}
    print(only, len(only), only == {None})
    n = 0
    while len(e) > 0:
        e.pop()
        n += 1
    print(n)


def ints() -> None:
    s: set[int | None] = {3, None, 1}
    print(s, len(s), None in s, 1 in s, 2 in s)
    k: int | None = 3
    print(k in s)
    k = None
    print(k in s)
    s.add(1)
    s.add(None)
    s.add(70000)
    print(s, len(s))
    s.remove(1)
    s.discard(5)
    s.discard(None)
    print(s, None in s)
    t: set[int | None] = {None, 3}
    print(s | t, s & t, s - t, t - s, s ^ t, s == t, {3, 70000} == {70000, 3})
    print(sorted([x for x in s if x is not None]))
    total = 0
    for x in t:
        if x is not None:
            total += x
        else:
            total += 100
    print(total)
    big: set[int | None] = set()
    for i in range(200):
        big.add(i * 7)
    big.add(None)
    print(len(big), None in big, 693 in big, 694 in big, sum([x for x in big if x is not None]))
    for i in range(0, 200, 2):
        big.remove(i * 7)
    print(len(big), None in big, 0 in big, 7 in big)


def tuples() -> None:
    s: set[tuple[int, str] | None] = set()
    s.add((1, "a"))
    s.add(None)
    s.add((1, "a"))
    print(len(s), None in s, (1, "a") in s, (2, "a") in s)
    k: tuple[int, str] | None = None
    print(k in s)
    k = (1, "a")
    print(k in s)
    s.discard(None)
    print(len(s), None in s)
    d: set[tuple[str | None, int] | None] = {(None, 1), None, ("x", 2)}
    print(len(d), None in d, (None, 1) in d, (None, 2) in d, ("x", 2) in d)


def byts() -> None:
    s: set[bytes | None] = {b"a", None}
    print(len(s), None in s, b"a" in s, b"b" in s)
    s.remove(b"a")
    print(s)


strs()
ints()
tuples()
byts()
