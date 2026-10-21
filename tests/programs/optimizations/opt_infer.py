# Inferred optional types: x if c else None, x or None, templates that return None and a value,
# displays that hold None among values, tuples of optional items returned item by item


def parse(line: str) -> tuple[str | None, str | None]:
    if line == "":
        return None, None
    if line.startswith("["):
        return line[1:-1], None
    if "=" in line:
        k, v = line.split("=", 1)
        return k.strip(), v.strip()
    return None, line.strip()


def keys(lines: list[str]) -> list[str]:
    seen = []
    for ln in lines:
        name, value = parse(ln)
        if name is not None and value is not None:
            seen.append(name + "=" + value)
        elif name is not None:
            seen.append("[" + name + "]")
        elif value is not None:
            seen.append("+" + value)
    return seen


def pick(xs, k):
    # a template: a str and None make str | None
    for x in xs:
        if x == k:
            return x
    return None


def lead(xs):
    # and None first
    if len(xs) == 0:
        return None
    return xs[0]


def main() -> None:
    for ln in ["", "[sec]", "k = v", "cont"]:
        print(parse(ln))
    print(keys(["[s]", "a=1", " more", ""]))
    none: list[str] = []
    print(pick(["a", "b"], "b"), pick(["a"], "z"), lead([[1], [2]]), lead(none), lead(["s"]))
    n = 3
    s = "big" if n > 2 else None
    t = None if n > 5 else [n]
    u = s or None
    print(s, t, u, s.upper() if s else "", t[0] if t is not None else -1)
    ws = ["a", None, "b"]
    vs = {"k": None, "j": "v"}
    print(ws, vs, [None, ("x", 1)], {"n": [1], "m": None})
    pair: tuple[str | None, list[int] | None] = ("p", None)
    print(pair, pair == ("p", None))


main()
