# A template's function whose empty container only code its argument types leave out fills
# (a loop over the empty tuple of *args, a branch an isinstance test removes) returns it empty:
# each call gives it the type its context expects (else list[int] or dict[int, int]); other
# reads of it give it that type too.
def collect(*args):
    out = []
    for a in args:
        out.append(a * 2)
    return out


print(collect(1, 2, 3))
print(collect())
print(sum(collect()), collect() == [], sorted(collect()), len(collect()))
for v in collect():
    print(v)


def strs(*args):
    out = []
    for a in args:
        out.append(str(a))
    return out


print(", ".join(strs()), strs(1, 2))
r: list[str] = strs()
r.append("z")
print(r)


def index(*args):
    d = {}
    for a in args:
        d[a] = len(d)
    return d


print(index("x", "y"), index())
e: dict[str, int] = index()
e["q"] = 1
f: dict[int, int] = index()
f[7] = 8
print(e, f)


def evens(x):
    out = []
    if isinstance(x, list):
        for v in x:
            if v % 2 == 0:
                out.append(v)
    return out


print(evens([1, 2, 4]), evens(3))


def total(*nums):
    acc = []
    for n in nums:
        acc.append(n)
    return sum(acc)


def pair(*args):
    out = []
    for a in args:
        out.append(a)
    return out, len(args)


def twice(*args):
    out = []
    for a in args:
        out.append(a)
    return out + out


def fmt(*args):
    parts = []
    for a in args:
        parts.append(str(a))
    return "-".join(parts)


def tail(*args):
    out = []
    for a in args:
        out.append(a)
    else:
        out.append(0)
    return out


print(total(1, 2), total(), pair(), twice(1), twice())
print(fmt(1, 2), "[" + fmt() + "]", tail(), tail(5))


def same(*args):
    out = []
    for a in args:
        out.append("x")
    return out


s = same()
s.append("y")
print(s, same(1))


def fresh() -> list[int]:
    out = []
    return out


def size(xs: list[str]) -> int:
    return len(xs)


def empty_size() -> int:
    tmp = []
    return size(tmp)


print(fresh(), empty_size())
