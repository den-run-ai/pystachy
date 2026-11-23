# A closed union may hold one tuple type beside scalars, lists and dictionaries: a result that
# is a value or a (value, log) pair. isinstance(x, tuple) narrows it; truth, len(), str(),
# repr() and equality select the member's.
def repair(s: str, logging: bool = False) -> str | tuple[str, list[str]]:
    if logging:
        return s, ["fixed"]
    return s


def pick(k: int) -> int | str | tuple[int, str] | list[int] | None:
    if k == 0:
        return 7
    if k == 1:
        return "seven"
    if k == 2:
        return (7, "seven")
    if k == 3:
        return [7, 7]
    return None


def results() -> None:
    a = repair("x")
    b = repair("y", True)
    if isinstance(a, str):
        print(a.upper())
    if isinstance(b, tuple):
        print(b[0], b[1])
        v, log = b
        log.append("again")
        print(v, log, len(b))
        print(b)
    if not isinstance(b, str):
        print(b[1])
    print(a)
    print(b)
    print(a == b, a == "x", b == ("y", ["fixed", "again"]), b != ("y", ["no"]))
    print(bool(a), bool(b), bool(repair("")), bool(repair("", True)))
    print(isinstance(a, tuple), isinstance(b, tuple), isinstance(b, str), isinstance(b, (str, tuple)))
    items: list[str | tuple[str, list[str]]] = [a, b, repair("z", True)]
    for it in items:
        if isinstance(it, tuple):
            it[1].append("more")
            print("tuple", it[0], it[1])
        else:
            print("str", it)
    print(items)


def members() -> None:
    vals = [pick(k) for k in range(5)]
    print(vals)
    for v in vals:
        print(repr(v), str(v), bool(v), v is None, isinstance(v, tuple), f"{v}|{v!r}")
        if v is not None and not isinstance(v, int):
            print(len(v))
    print(vals[2] == (7, "seven"), vals[2] == vals[2], vals[2] == vals[1], vals[2] != (7, "x"), (7, "seven") == vals[2])
    print((7, "seven") in vals, vals.index((7, "seven")), vals.count(None))
    try:
        print(len(vals[0]))
    except TypeError as e:
        print("TypeError", e)
    try:
        print(len(vals[4]))
    except TypeError as e:
        print("TypeError", e)


def stores(c: bool) -> None:
    d: dict[str, int | tuple[int, str]] = {"a": 1, "b": (2, "two")}
    print(d, d["b"] == (2, "two"), d["a"] == (2, "two"))
    e: int | tuple[float, ...] = (1.5, 2.5, 3.5)
    print(e, len(e) if isinstance(e, tuple) else -1)
    e = 4
    print(e)
    f: str | tuple[()] = ()
    print(f, bool(f), len(f))
    y: int | tuple[int, str] = 5
    if c:
        y = (2, "b")
    print(y, isinstance(y, tuple))
    z: float | tuple[float, float] = (1.5, 2.5)
    print(z)
    w: str | tuple[str, list[str]] = ("a", [])
    if isinstance(w, tuple):
        w[1].append("x")
    print(w)
    u: int | tuple[int, ...] = (1, 2, 3)
    if isinstance(u, tuple):
        print(sum(u), u[1], [x * 2 for x in u])


class Outcome:
    def __init__(self, value: bool | tuple[bool, str]) -> None:
        self.value = value

    def ok(self) -> bool:
        v = self.value
        if isinstance(v, tuple):
            return v[0]
        return v


results()
members()
stores(True)
stores(False)
print(Outcome(True).ok(), Outcome((False, "why")).ok(), Outcome((True, "")).value)
