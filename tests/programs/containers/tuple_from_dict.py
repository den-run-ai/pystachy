# tuple() of a dict (its keys, in order) or a set, and membership in a runtime-length tuple.
D = {"[": "]", "{": "}", "(": ")"}
OPENERS = tuple(D)
print(OPENERS, "[" in OPENERS, len(OPENERS))


def main() -> None:
    d: dict[int, str] = {3: "c", 1: "a", 2: "b"}
    t = tuple(d)
    d[9] = "z"
    print(t, len(t), t[0], 9 in t)
    s = {7}
    u = tuple(s)
    s.add(8)
    print(u)
    f = frozenset(["only"])
    print(tuple(f))
    e: dict[str, int] = {}
    print(tuple(e), tuple(e) == ())
    for opener in tuple(D):
        print(opener, D[opener])
    print(tuple([1, 2]), tuple("ab"), tuple(range(3)))


main()


def member(c: str | None, n: int) -> list[bool]:
    t = tuple(D)
    nums = tuple([1, 2, 3])
    fl = tuple([1.0, 2.5])
    return [c in t, c not in t, n in nums, n not in nums, n in fl, 2.5 in fl, 1.0 in nums, None in t, "(" in OPENERS, "x" not in OPENERS]


print(member("[", 1), member(None, 7), member("z", 2))
