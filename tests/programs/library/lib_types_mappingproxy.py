# types.MappingProxyType: a read-only view of a dict, which reads the dict's items as they are
# when it is read, as tomllib's escape table and tomli-w's do
import types
from types import MappingProxyType

ESCAPES = MappingProxyType({"\\n": "\n", "\\t": "\t", '\\"': '"'})


def unescape(s: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(s):
        two = s[i : i + 2]
        if two in ESCAPES:
            out.append(ESCAPES[two])
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


print(repr(unescape('a\\tb\\n\\"c\\"')))
try:
    print(ESCAPES["\\q"])
except KeyError as e:
    print("KeyError", e)

# reads, and the dict's changes, which the view shows
d = {"b": 2, "a": 1}
m = MappingProxyType(d)
print(m["a"], len(m), "a" in m, "z" in m, "z" not in m, bool(m))
print(m.get("a"), m.get("z"), m.get("z", 0))
print(list(m), sorted(m), [k for k in m], list(reversed(m)), max(m))
print(list(m.keys()), list(m.values()), list(m.items()))
for k, v in m.items():
    print(k, v)
d["c"] = 3
del d["b"]
print(m, len(m), m["c"], "b" in m)
print(repr(m), str(m), f"{m} {m!r}")
print(type(m).__name__, isinstance(m, MappingProxyType), isinstance(m, types.MappingProxyType))

# copies: a dict, which the view's dict does not share
c = m.copy()
c["x"] = 9
print(c, m, type(c).__name__)
u = m | {"z": 26}
print(u, m | MappingProxyType({"a": 0}), type(u).__name__)

# equality: of the dict, with a dict or another view
print(m == {"a": 1, "c": 3}, m == {"a": 1}, m != {"a": 1}, m == MappingProxyType({"c": 3, "a": 1}))
print(m == m, m != MappingProxyType(d), MappingProxyType(d) == d)

# what a view cannot do
try:
    m |= {"q": 1}
except TypeError as e:
    print("TypeError", e)
try:
    print(hash(m))
except TypeError as e:
    print("TypeError", e)
try:
    for k in m:
        d[k + k] = 0
except RuntimeError as e:
    print("RuntimeError", e)
print(m)


# annotations name its types; a view of an empty dict takes them from one
def total(counts: MappingProxyType[str, int]) -> int:
    n = 0
    for k in counts:
        n += counts[k]
    return n


def names(table: types.MappingProxyType[int, str]) -> str:
    return ",".join([table[k] for k in sorted(table)])


print(total(MappingProxyType({"x": 4, "y": 5})), names(MappingProxyType({3: "c", 1: "a"})))
empty: MappingProxyType[str, int] = MappingProxyType({})
print(empty, len(empty), total(empty), empty.get("k"))
named = MappingProxyType(mapping={"k": 11})
print(named["k"], MappingProxyType[str, int]({"z": 26}))


class Point:
    def __init__(self, x: int) -> None:
        self.x = x

    def __repr__(self) -> str:
        return f"Point({self.x})"


points = MappingProxyType({"o": Point(0), "p": Point(5)})
print(points, points["p"].x, [p.x for p in points.values()])
