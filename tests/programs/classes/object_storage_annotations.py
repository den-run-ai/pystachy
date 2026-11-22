# object in other annotations: a module variable, a class attribute, object | None and
# Optional[object] (object holds None already), int | object (object), list[object] | None, *args
# and **kwargs, the values of a union and of an int | None stored as object, and a conditional
# expression of two types where an object is wanted
from typing import Optional

G: object = "global"
CACHE: dict[int, object] = {}


class Cfg:
    default: object = None

    def __init__(self, v: object) -> None:
        self.v: object = v


def get(flag: bool) -> object | None:
    return 1 if flag else None


def opt(flag: bool) -> Optional[object]:
    return "y" if flag else None


def mixed(flag: bool) -> int | object:
    return 2 if flag else "two"


def setg(v: object) -> None:
    global G
    G = v


def varargs(*args: object, **kw: object) -> str:
    return f"{len(args)} {args} {kw}"


def main() -> None:
    print(G, get(True), get(False), opt(True), opt(False), mixed(True), mixed(False))
    setg(3.5)
    print(G)
    CACHE[1] = [1]
    CACHE[2] = None
    print(CACHE)
    c = Cfg(10)
    c2 = Cfg("s")
    print(c.v, c2.v, Cfg.default, [c.v, c2.v])
    u: int | str = 5
    o: object = u
    print(o, o == 5)
    u = "five"
    o = u
    print(o, o == "five")
    mb: int | None = None
    o = mb
    print(o, o is None)
    mb = 4
    o = mb
    print(o, o == 4)
    xs: list[object] | None = None
    print(xs)
    xs = [1, None]
    print(xs)
    k = 3
    w = o if k > 2 else "w"
    print(w)
    print(varargs(), varargs(1, "a", None, k=2.5), varargs(*[1, 2], **{"x": "y"}))


main()
