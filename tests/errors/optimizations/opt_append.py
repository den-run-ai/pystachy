# error: argument 1 of list.append() may be None (str | None); test it with 'is not None' first
def collect(xs: list[str | None]) -> list[str]:
    out: list[str] = []
    for x in xs:
        out.append(x)
    return out


print(collect(["a", None]))
