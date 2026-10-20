# Optional str, list, dict and tuple values: annotations in every spelling, returns, printing,
# truth, comparisons with None and with values
from typing import Optional, Union
import typing


def first(xs: list[str], prefix: str) -> str | None:
    for x in xs:
        if x.startswith(prefix):
            return x
    return None


def nothing(n: int) -> None | list[int]:
    if n > 0:
        return [n]
    # falls off its end: None, as CPython returns


def maybe_dict(k: str) -> Optional[dict[str, int]]:
    if k == "":
        return None
    return {k: len(k)}


def pair(flag: bool) -> typing.Optional[tuple[str, int]]:
    return ("p", 1) if flag else None


def either(a: Union[str, None], b: Union[None, list[str]], c: Optional[str | None]) -> str:
    return f"{a} {b} {c}"


def bare(flag: bool) -> str | None:
    if flag:
        return
    return "x"


def show(label: str, v: str | None) -> None:
    print(label, v, repr(v), str(v), f"[{v}] [{v!r}] [{v:>6}]" if v is not None else f"[{v}] [{v!r}]", "%s|%r|%5s" % (v, v, v))


def main() -> None:
    a = first(["bob", "alice", "al"], "al")
    b = first(["bob"], "al")
    show("a", a)
    show("b", b)
    print(either(None, None, None), either("a", ["b"], "c"))
    print(nothing(2), nothing(0), maybe_dict("abc"), maybe_dict(""), pair(True), pair(False), bare(True), bare(False))
    for v in [a, b, "", "x"]:
        print(repr(v), bool(v), not v, "yes" if v else "no", v is None, v is not None, v == None, v != None)
    print(a == "alice", a == b, b == None, b == b, a != "x", "alice" == a, None == b, a < "b", a >= "alice")
    xs = nothing(3)
    ys = nothing(0)
    print(xs == [3], ys == [3], xs == ys, ys == None, bool(xs), bool(ys))
    d = maybe_dict("hi")
    e = maybe_dict("")
    print(d == {"hi": 2}, e == d, bool(d), bool(e), d is not None and "hi" in d)
    t = pair(True)
    u = pair(False)
    print(t, u, t == ("p", 1), u == t, bool(t), bool(u))
    z: str | None = None
    print(z, z or "default", z and z.upper())
    z = "zed"
    print(z, z or "default", z and z.upper(), (z or "") + "!")
    w: list[str] | None = []
    print(w, bool(w), w is None)
    empty: str | None = ""
    print(repr(empty), empty or "was empty", repr(empty and "no"))


main()
