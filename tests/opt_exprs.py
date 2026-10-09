# Expressions with None and optional values: None or x, None and x, conditionals of None, a
# comprehension's own variables (which do not end the narrowing of an outer local), a template
# whose first return is None, and locals first assigned None typed by later values or by the
# context that reads them (or always None)


def need(s: str) -> str:
    return "<" + s + ">"


def g() -> None:
    print("g")


def ors(s: str) -> None:
    print(None or s, None and s, None or "", g() or "x")


def conds(c: bool, d: bool) -> None:
    x = "a" if c else ("b" if d else None)
    y = None if c else None
    print(x, y is None, "p" if c else None if d else "q")


def scope(x: str | None, ys: list[str | None]) -> None:
    if x is not None:
        zs = [x for x in ys]
        n = sum(1 for x in ys if x is None)
        print(need(x), zs, n)


def find(xs, i, k):
    if i >= len(xs):
        return None
    if xs[i] == k:
        return xs[i]
    return find(xs, i + 1, k)


def later(y: str | None, c: bool) -> None:
    x = None
    x = [y]
    t = None
    if c:
        t = (y, 1)
    d = None
    d = {"a": y}
    print(x, t, d)


def ctx(s: str | None) -> str | None:
    x = None
    print(need(str(x)), x, x is None, s)
    ys: list[str | None] = []
    y = None
    ys.append(y)
    print(ys)
    return x


ors("s")
conds(True, False)
conds(False, False)
conds(False, True)
scope("a", [None, "b"])
print(find(["a", "b"], 0, "b"), find(["a"], 0, "z"))
later(None, True)
later("q", False)
print(ctx(None))
