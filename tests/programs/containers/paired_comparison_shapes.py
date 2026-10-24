# These typed comparisons retain their separate descriptors; no dynamic opt-in.
def compare(flag: bool) -> None:
    integers: tuple[int, ...] = (1, 2)
    reals = (1.0, 2.0)
    words: tuple[str, ...] = ("one", "two")
    empty: tuple[str, ...] = ()
    fixed = (1, 2)
    value: int | list[int] = 1 if flag else [1, 2]
    optional: int | list[int] | None = value if flag else None
    print("tuples", integers == reals, reals == integers,
          fixed == words, words == fixed, integers != words)
    print("empty", empty == (), () == empty, empty != ())
    print("union", value == fixed, fixed == value, value != words,
          optional == fixed, fixed == optional, optional != empty)


compare(False)
compare(True)
for filled in [False, True]:
    a: set[tuple[int, str]] = set()
    b: set[tuple[str, str]] = set()
    c: set[tuple[tuple[int, int], bytes]] = set()
    d: set[tuple[tuple[int, str], bytes]] = set()
    e: set[tuple[int, int, int]] = set()
    if filled:
        a.add((0, ""))
        b.add(("", ""))
        c.add(((0, 0), b""))
        d.add(((0, ""), b""))
        e.add((0, 0, 0))
    fb: frozenset[tuple[str, str]] = frozenset(b)
    print("tuple sets", filled, a == b, b == a, a != b, b != a,
          a == fb, fb == a, c == d, d == c, a == e, e == a)
    print("numeric overlap", {(1, 2)} == {(1, int(True) + 1)})
