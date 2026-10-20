# int | None, float | None and bool | None: a pointer to an immutable box of the value, None
# null. Annotations, inferred locals, fields, NamedTuples, globals, templates, truth, printing,
# formatting, dict.get() and dict.pop() of int, float and bool values
from dataclasses import dataclass
from typing import NamedTuple, Optional, TypeVar, Union

T = TypeVar("T")


def first(xs: list[T], d: T | None = None) -> T | None:
    return xs[0] if xs else d


def lineof(sources: dict[tuple[str, str | None], int], section: str, name: str | None = None) -> int | None:
    # (iniconfig's IniConfig.lineof)
    lineno = sources.get((section, name))
    return None if lineno is None else lineno + 1


def flag(f: None | bool) -> str:
    return f"{f}"


@dataclass
class Item:
    name: str
    qty: int | None = None
    price: Optional[float] = None


class P(NamedTuple):
    x: int
    y: int | None


def tmpl(n):
    if n < 0:
        return None
    return n * 2


def tmpl2(n):
    if n > 0:
        return n + 0.5
    return None


def ends(n: int) -> int | None:
    if n > 1:
        return n


def first_none(xs: list[int]) -> Union[int, None]:
    for x in xs:
        if x < 0:
            return x
    return None


best: int | None = None


def update(v: int) -> None:
    global best
    if best is None or v > best:
        best = v


src: dict[tuple[str, str | None], int] = {("a", None): 0, ("a", "x"): 3}
print(lineof(src, "a"), lineof(src, "a", "x"), lineof(src, "b"), flag(None), flag(True))
x: Optional[int] = None
print(x, x is None, x == None, x != None, repr(x), str(x), f"{x}|{x!r}", "%s" % x)
x = 5
print(x, x + 1 if x is not None else -1, x == 5, 5 == x, x != 4, x < 6, f"{x:>4}|{x:+d}|{x:x}", "%3d" % x)
f: Union[float, None] = 2.5
b: bool | None = True
print(f, b, repr(f), str(b), f"{f}|{b}", f"{f:.3f}", "%.1f %s" % (f, b))
seen = {}
for w in ["a", "b", "a"]:
    if seen.get(w):
        print("dup", w)
    seen[w] = True
tk = {(1, "a"): 1}
print(tk.get((1, "a"), None), tk.get((2, "b"), None), tk.get((1, "a")))
it = Item("pen")
print(it, it.qty, Item("a", 3, 1.5), Item("a", 3) == Item("a", 3), Item("a") == Item("a", 0))
it.qty = 4
it.price = None
print(it)
p = P(1, None)
q = P(1, 2)
print(p, q, p == q, p == P(1, None), p.y, q.y)
print(tmpl(3), tmpl(-1), tmpl2(1), tmpl2(-1), ends(5), ends(0), first_none([1, -2]), first_none([1]))
for v in [3, 1, 7, 2]:
    update(v)
print(best)
def lens(ws: list[str]) -> None:
    n = None
    for w in ws:
        n = len(w)
    print(n)
    m = None
    if n is not None and n > 2:
        m = n * 10
    print(m, m or 0, m and 5, n or None, 0 or None)


lens(["ab", "cde"])
lens([])
z: int | None = 0
print(z or 7, z is None, bool(z), not z)
z = None
print(z or 7, bool(z), not z)
k: int | None = None
total = 0
for i in range(5):
    if k is None:
        k = i
    else:
        k += i
    total += k
print(k, total)
c: float | None = 1.0
if c:
    c *= 2.5
print(c, isinstance(c, float), isinstance(c, int))
flags: dict[str, bool] = {"a": True, "b": False}
print(flags.get("a"), flags.get("b"), flags.get("c"), flags.pop("a", None), flags.pop("zz", None), flags)
fl: dict[int, float] = {1: 0.5}
dflt: float | None = None
print(fl.get(1), fl.get(2), fl.get(2, dflt), fl.get(1, dflt), fl.get(3, None))
t3: tuple[int | None, str] = (1, "a") if total > 3 else (None, "b")
print(t3, t3[0])
vals: list[int | None] = [None, 2]
print(max(1, 2) if vals[1] is None else vals[1] + 1, [v for v in vals if v is not None], [v is None for v in vals])
print(sorted([3, 1, 2]), min([4, 2]), int(vals[1] or 0), float(vals[1] or 0))
s = vals[1]
if s is not None:
    print(int(s) + 1, float(s), str(s), -s, abs(s), round(c))
print("%d %s %r %5.1f" % (vals[1], vals[0], vals[1], c))
dd = {"a": 1, "b": None}
xs = [1, None, 3]
fs = [None, 2.5]
print(dd, xs, fs, sorted(dd.items(), reverse=True), [x for x in xs])
print(first([1, 2]), first([2.5]), first([True]))
e: list[int] = []
print(first(e), first(e, 7))
