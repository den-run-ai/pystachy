# Narrowing after loops: the state after a loop is what holds where its test is false and at
# each break that leaves it; after a loop with an else block, at the end of the else block and
# at each break (which skips it)


def need(s: str) -> str:
    return "<" + s + ">"


def until(x: str | None) -> str:
    while True:
        if x is not None:
            break
        x = "d"
    return need(x)


def first(xs: list[str], x: str | None) -> str:
    while x is None:
        x = xs.pop()
    return need(x)


def found(words: list[str], w: str) -> str:
    hit: str | None = None
    for v in words:
        if v == w:
            hit = v
            break
    else:
        return "missing"
    return need(hit)


def counted(x: str | None) -> str:
    i = 0
    while i < 3:
        i += 1
        if x is not None and i == 2:
            break
    else:
        if x is None:
            return "none"
    return need(x)


def drop(x: str | None, ys: list[str | None]) -> None:
    while x is not None:
        print("drop", need(x))
        x = ys.pop() if len(ys) > 0 else None
    print("dropped", x)


print(until(None), until("q"), first(["a", "b"], None), first([], "c"))
print(found(["a", "b"], "b"), found(["a"], "z"))
print(counted("x"), counted(None))
drop("p", [None, "r"])


def asserted(x: str | None) -> str:
    if x is None:
        assert False, "nope"
    return need(x)


print(asserted("z"))
