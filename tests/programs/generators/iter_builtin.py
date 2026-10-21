# iter() and next(): the iterators of lists, strings, tuples, dicts and their keys(), values()
# and items(), sets, ranges and files, first-class values whose position every use shares, as
# CPython's; an exhausted iterator stays exhausted; a dict or set that changes size fails it.
import os
import tempfile
from typing import Iterator, NamedTuple


class Seq:
    def __init__(self) -> None:
        self.items = ["p", "q", "r"]

    def __iter__(self) -> Iterator[str]:
        return iter(self.items)


class Plain:
    # an unannotated __iter__ returning iter() of a list: the list's iterator object
    def __init__(self) -> None:
        self.items = [3, 4]

    def __iter__(self):
        return iter(self.items)


class P(NamedTuple):
    x: int
    y: int


def pairs(xs):
    it = iter(xs)
    out = []
    for a in it:
        out.append((a, next(it, a)))
    return out


xs = [1, 2, 3, 4]
it = iter(xs)
print(next(it), iter(it) is it)
for x in it:
    print("x", x)
    if x == 3:
        break
print(list(it), next(it, -1), list(it))
xs.append(5)
print(next(it, -2), list(it))
it2 = iter(xs)
print(next(it2))
xs.append(6)
print(list(it2), 6 in iter(xs), 9 in iter(xs))
it3 = iter(xs)
print(4 in it3, list(it3))
print(list(zip(iter(xs), iter(xs))))
xi = iter(xs)
print(list(zip(xi, xi)))
names = ["é", "ü", "ß"]
ni = iter(names)
print(next(ni), " ".join(ni))

s = iter("hello")
print(next(s), next(s), "".join(s), next(s, "?"))
t = iter((1, 2, 3))
print(next(t), list(t), list(t))
pt = iter(P(5, 6))
print(next(pt), list(pt))

d = {"a": 1, "b": 2}
k = iter(d)
print(next(k), list(k), list(k))
v = iter(d.values())
print(next(v), next(v), next(v, 0))
items = iter(d.items())
print(next(items), list(items))
k2 = iter(d.keys())
next(k2)
d["c"] = 3
try:
    next(k2)
except RuntimeError as e:
    print("RuntimeError:", e)
d["z"] = 0
del d["z"]
try:
    next(k2)
except RuntimeError as e:
    print("RuntimeError again:", e)
e2 = {0: "a", 1: "b"}
k3 = iter(e2)
print(next(k3))
del e2[0]
e2[2] = "c"
print(next(k3))
try:
    print(list(k3))
except RuntimeError as e:
    print("RuntimeError:", e)
print(list(k3), next(k3, -1))
v2 = iter({1: 1}.values())
print(list(v2), next(v2, -1))

st = {7}
si = iter(st)
print(next(si), next(si, None))
st2 = {1, 2}
si2 = iter(st2)
next(si2)
st2.add(3)
try:
    next(si2)
except RuntimeError as e:
    print("RuntimeError:", e)
fs = frozenset([4])
print(list(iter(fs)))

r = iter(range(10, 0, -3))
print(next(r), list(r), list(r))
print(sum(iter(range(5))), list(iter(range(0))), next(iter(range(3, 4))))
big = iter(range(9223372036854775806, 9223372036854775807))
print(list(big))
try:
    iter(range(1, 5, 0))
except ValueError as e:
    print("ValueError:", e)

b = Seq()
bi = iter(b)
print(next(bi), list(bi))
pl = Plain()
print(list(pl), next(iter(pl)), [y for y in pl])
for w in Seq():
    print(w)
print(pairs([1, 2, 3, 4, 5]), pairs("abc"))
a1, a2 = iter([10, 20])
print(a1, a2)
try:
    a1, a2 = iter([1, 2, 3])
except ValueError as e:
    print("ValueError:", e)
empty: list[str] = []
print(next(iter(empty), "empty"))

tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "lines.txt")
f = open(path, "w")
f.write("first\nsecond\nthird\nfourth\n")
f.close()
f = open(path)
print(iter(f) is f, repr(next(f)))
header = next(f)
for line in f:
    print("line", repr(line))
    break
print([ln.strip() for ln in iter(f)], repr(next(f, "eof")), next(f, None))
f.close()
try:
    iter(f)
except ValueError as e:
    print("ValueError:", e)
os.remove(path)
os.rmdir(tmp)
print(next(iter(empty)))
