# An append in place (#112) must not change a str that anything else holds: every read of the
# local but len() lets the str escape, and the next append copies it. Aliases, s += s, reads in
# the loop (print, comparisons, slicing, strip, f-strings, dict keys, sets, calls that keep it),
# closures, comprehensions, rebinding, stores while s owns its str, and operands that are no str.
kept: list[str] = []


def keep(s: str) -> int:
    kept.append(s)
    return len(kept)


class Holder:
    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, s: str) -> None:
        self.items.append(s)


def alias() -> None:
    s = "ab"
    s += "c"
    y = s
    s += "x"
    print(y, s, y is s)
    z = s
    s = s + "y"
    print(z, s)
    s += s
    print(s)
    s += s + s[1:3]
    print(s)
    held: list[str] = []
    s = "h"
    s += "-"
    s += stash(held, s)
    s += stash(held, "-")
    print(held, s)


def stash(xs: list[str], s: str) -> str:
    xs.append(s)
    return "!"


def reads() -> None:
    s = ""
    seen: list[str] = []
    h = Holder()
    d: dict[str, int] = {}
    st: set[str] = set()
    for i in range(6):
        s += str(i)
        if i == 1:
            print("print", s)
        if s == "012":
            seen.append("eq")
        if s < "0124":
            seen.append(s[:])
        seen.append(s[-2:])
        seen.append(s.strip())
        seen.append(f"{s}")
        d[s] = i
        st.add(s)
        h.add(s)
        keep(s)
    print(seen)
    print(d)
    print(sorted(st))
    print(h.items)
    print(kept)


def lengths() -> None:
    s = "-"
    ns: list[int] = []
    for i in range(5):
        s += "ab"
        ns.append(len(s))
        if len(s) > 6:
            s += "!"
    print(s, ns)


def returned(n: int) -> str:
    s = "r"
    for i in range(n):
        s += str(i)
    return s


def caller() -> None:
    a = returned(3)
    b = a
    a += "x"
    print(a, b)
    rs = [returned(2), returned(2)]
    for j in range(2):
        r = rs[j]
        r += "!"
        print(r, rs)
    for j in range(2):
        r = rs[j]
        r += "?"
    print(rs)
    for q in rs:
        q += "#"
    print(rs)


def closure() -> None:
    s = "c"
    got: list[str] = []

    def get() -> str:
        return s

    for i in range(3):
        s += str(i)
        got.append(get())
    print(got, s)
    f = lambda: s + "?"
    s += "z"
    print(f(), s)


def comprehension() -> None:
    s = "q"
    out: list[str] = []
    for i in range(3):
        s += "+"
        out += [s for _ in range(2)]
        out += [x for x in [s]]
    print(out)
    names = ["a", "b"]
    s = ""
    for k in range(2):
        s += "".join([s for s in names])
        s += str(k)
    print(s)


def rebinding() -> None:
    s = ""
    for w in ["x", "y", "z"]:
        s += w
    t = s
    for s in ["one", "two"]:
        s += "!"
        print(s, t)
    a, s = s, "fresh"
    s += "?"
    print(a, s, t)
    del s
    s = "back"
    s += "."
    print(s)
    s = "e"
    try:
        int("bad")
    except ValueError as s:
        print("caught", type(s).__name__)
    s = "after"
    s += "!"
    print(s)


def stores() -> None:
    # stores to s while it owns its str: for targets and unpacking must clear the flag
    lst = ["one" + str(i) for i in range(3)]
    s = ""
    s += "a"
    for s in lst:
        s += "!"
    print(lst, s)
    s += "b"
    for i, s in enumerate(lst):
        s += "?"
    print(lst, s, i)
    s += "c"
    for s, n in zip(lst, [1, 2]):
        s += "#"
    print(lst, s, n)
    pair = ("left" + str(n), 3)
    s += "d"
    s, n = pair
    s += "!"
    print(pair, s, n)
    s += "e"
    s, *rest = lst
    s += "!"
    print(lst, s, rest)
    s += "f"
    *rest, s = lst
    s += "!"
    print(lst, s, rest)


def walrus() -> None:
    s = "w"
    s += "1"
    t = ""
    s += (t := s)
    print(s, t)
    s += "2"
    print(s, t)


def through(n: int) -> list[str]:
    out: list[str] = []
    s = "t"
    for i in range(n):
        s += "."
        out.append(s)
        s += "-"
    return out


def param_alias(p: str) -> str:
    p += "!"
    return p


def params() -> None:
    s = "base"
    s += "+"
    u = param_alias(s)
    print(s, u)
    s += "more"
    print(s, u, param_alias(s))


alias()
reads()
lengths()
caller()
closure()
comprehension()
rebinding()
stores()
walrus()
print(through(4))
params()
