# Narrowing: where a local or parameter of type T | None is known to hold a T, it can be passed
# where only a T may go (as mypy narrows it)
import sys


def need(s: str) -> str:
    return "<" + s + ">"


def lst(xs: list[int]) -> int:
    return sum(xs)


def find(words: list[str], w: str) -> str | None:
    return w if w in words else None


def tests(x: str | None, ys: list[int] | None) -> None:
    if x is not None:
        print("is not None", need(x))
    if x:
        print("truthy", need(x))
    if not x:
        print("falsy", x)
    else:
        print("else of not", need(x))
    if x is None:
        print("none")
    elif len(x) > 3:
        print("elif long", need(x))
    else:
        print("elif short", need(x))
    if x != None and ys is not None:
        print("both", need(x), lst(ys))
    if x is None or ys is None:
        print("one is None")
    else:
        print("neither", need(x), lst(ys))
    print("and", x is not None and need(x) == "<ab>", ys is not None and lst(ys) > 1)
    print("or", x is None or need(x) == "<ab>")
    print("ifexp", need(x) if x is not None else "-", need(x) if x else "--", "-" if x is None else need(x))
    if isinstance(x, str):
        print("isinstance", need(x))


def early(x: str | None) -> str:
    if x is None:
        return "early"
    return need(x)


def raised(x: str | None) -> str:
    if x is None:
        raise ValueError("no x")
    return need(x)


def exited(x: str | None) -> str:
    if not x:
        sys.exit("no x")
    return need(x)


def asserted(x: str | None) -> str:
    assert x is not None, "x is None"
    return need(x)


def assigned(x: str | None) -> str:
    if x is None:
        x = "default"
    return need(x)


def looped(xs: list[str | None]) -> list[str]:
    out: list[str] = []
    for x in xs:
        if x is None:
            continue
        out.append(need(x))
    for x in xs:
        if not x:
            break
        out.append(need(x))
    i = 0
    while i < len(xs):
        y = xs[i]
        i += 1
        if y is None:
            continue
        out.append(y)
    return out


def walk(start: str | None) -> int:
    n = 0
    cur = start
    while cur is not None:
        n += len(cur)
        cur = cur[1:] if len(cur) > 1 else None
    return n


def comp(xs: list[str | None]) -> list[str]:
    return [need(s) for s in xs if s is not None] + [s.upper() for s in xs if s]


def fallback(x: str | None) -> str:
    y = x or "fallback"
    return need(y)


def annotated() -> str:
    z: str | None = "init"
    return need(z)


tests("ab", [1, 2])
tests(None, None)
tests("", [])
tests("abcd", None)
print(early(None), early("e"), raised(""), raised("r"), exited("x"), asserted("a"), assigned(None), assigned("given"))
print(looped(["a", None, "b", "", "c"]), walk("abc"), walk(None))
print(comp(["x", None, "", "y"]), fallback(None), fallback(""), fallback("f"), annotated())
print(asserted(None))
