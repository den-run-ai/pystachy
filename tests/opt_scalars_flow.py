# Optional ints, floats and bools in control flow: templates that return None and a number in
# either order, narrowing, conditional and boolean expressions, containers and their methods,
# comparisons with None and with numbers, slices with bounds that may be None, keys that may be None
def int_then_none(n):
    if n > 0:
        return n
    if n == 0:
        return 0
    return None


def none_then_float(x):
    if x < 0:
        return None
    if x == 0:
        return 0.0
    return x / 2


def bool_or_none(s):
    if s == "":
        return None
    return s == "y"


def deep(n: int) -> int | None:
    if n > 3:
        return None
    r = deep(n + 1)
    return n if r is None else r + n


def until(xs: list[int | None]) -> int:
    i = 0
    total = 0
    v = xs[i]
    while v is not None:
        total += v
        i += 1
        v = xs[i]
    return total


def first(xs: list[int]) -> int | None:
    for x in xs:
        if x % 2 == 0:
            return x
    return None


def use(xs: list[int]) -> str:
    f = first(xs)
    if f is None:
        return "none"
    assert f is not None
    return str(f * 10)


def pick(c: bool, x: int) -> int | None:
    return x if c else None


def pick2(c: int, x: float) -> float | None:
    return None if c == 0 else x if c == 1 else -x if c == 2 else None


def ret_tuple(n: int) -> tuple[int | None, str]:
    if n > 0:
        return n, "pos"
    t = (0, "zero")
    if n == 0:
        return t
    return None, "neg"


def dflt(x: int | None = 5, y: float | None = None) -> str:
    return f"{x}/{y}"


print(int_then_none(3), int_then_none(0), int_then_none(-1))
print(none_then_float(-1.0), none_then_float(0.0), none_then_float(5.0))
print(bool_or_none(""), bool_or_none("y"), bool_or_none("n"))
print(deep(0), deep(5))
print(until([1, 2, 3, None]), until([None]))
print(use([1, 3, 4]), use([1]))
print(pick(True, 3), pick(False, 3), pick2(0, 1.5), pick2(1, 1.5), pick2(2, 1.5), pick2(3, 1.5))
print(ret_tuple(1), ret_tuple(0), ret_tuple(-1))
print(dflt(), dflt(None), dflt(3, 2.0), dflt(y=1.5))
xs: list[int | None] = [4, None, 2]
print([x + 1 for x in xs if x is not None], sum(x for x in xs if x is not None))
ys: list[int | None] = [3, 1, 2]
ys.sort()
print(ys, sorted(ys, reverse=True), max(ys), min(ys), ys.index(2), ys.pop(), ys)
dd: dict[str, int | None] = {"a": 1, "b": None}
print(dd.get("a"), dd.get("b"), dd.get("c"), dd.pop("a", None), dd.pop("q", None), dd)
dd["c"] = 7
dd["d"] = None
print(dd, len(dd), "c" in dd, dd["c"], dd["d"])
n: int | None = 3
print(n in [1, 2, 3], n in {3: "x"}, n not in [1], None in [n], n in (1, 3))
n = None
print(n in [1, 2, 3], n in {3: "x"}, n not in [1], None in [n])
fs: list[float | None] = [1.5, None]
print(fs, fs == [1.5, None], fs != [1.5, None], fs < [2.0, None], [None, 1] == [None, 1])
bs: list[bool | None] = [True, None, False]
print(bs, bs.count(False), bs.count(None), True in bs)
tt: tuple[int | None, float | None, bool | None] = (None, 2.0, None)
print(tt, tt == (None, 2.0, None), tt[1])
z: int | None = None
k = 0
while k < 3:
    if z is None:
        z = k
    else:
        z = z * 10 + k
    k += 1
print(z)
d = {1: "a", 2: "b"}
kk: int | None = 1
print(d[kk], d.get(kk), d.get(kk, "z"), d.pop(kk, "q"), d)
kk = None
print(d.get(kk), d.get(kk, "z"), d.pop(kk, "q"), kk in d, d)
counts = {1: 10}
key: int | None = 1
print(counts.get(key), counts.pop(key, None), counts)
a: int | None = None
b: int | None = None
c: float | None = 1.0
print(a == b, a != b, a == 1, 1 == a, c == 1, 1 == c, c != None, a == c, 0 < 1 < c, a is None)
b = 1
print(a == b, b == 1, b == True, b != 1.0, b <= c, c > b)
lo: int | None = None
hi: int | None = 2
seq = [1, 2, 3]
print(seq[lo:], seq[:lo], seq[hi:lo], "abc"[lo:hi], seq[-1:lo], seq[lo:hi], seq[lo:-9223372036854775808])
dv: dict[str, int] = {"a": 1}
pair = (dv.get("a"), dv.get("b"))
p0, p1 = pair
print(p0, p1, pair, pair == (1, None))
print(d[kk])
