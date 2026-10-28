# pystachy: python-int
# The values of a dict that are tuples of ints hold promoting ints (docs/python-int.md): displays,
# comprehensions, item assignment, setdefault(), get() and pop() with defaults, update(), dict()
# of pairs, dict.fromkeys() and copies store them; indexing, unpacking, get(), pop(), popitem() and
# iteration over values() and items() read them; values(), items(), sorting, searches, comparisons
# and repr() take them; nested tuples, tuples of an int and a str, int keys and -2**63; and a module
# that does not opt in (fixed_dict_values), which reads and stores the values that fit and makes
# values that hold -2**63.
import sys
from fixed_dict_values import edge, first_value, made, put, total

ONE = len(sys.argv) - 2  # (1, which the compiler does not know)
BIG = 2 ** 64 * ONE
EDGE = -2 ** 63 * ONE


def pair(a: int, b: int) -> tuple[int, int]:
    return a, b


# stores
d = {"a": (BIG, 1), "b": (2, 3), "c": pair(EDGE, 4)}
d["d"] = (BIG * BIG, -1)
d["b"] = (5, BIG)
print(d, len(d))
c = {k: (v[0] + 1, v[1]) for k, v in d.items()}
print(c)
print(d.setdefault("e", (6, BIG)), d.setdefault("a", (0, 0)))
print(d.get("a", (0, 0)), d.get("zz", (BIG, 7)), d.get("zz", pair(EDGE, 8)))
print(d.pop("e"), d.pop("zz", (BIG, 9)), d.pop("zz", pair(EDGE, 9)))
d.update({"f": (BIG + 2, 0)})
d.update([("g", (1, BIG))])
print(d)
print(dict.fromkeys(["x", "y"], (BIG, 1)), dict([(1, (BIG, 2))]), dict(zip("ab", [(BIG, 3), (4, 5)])))
e = d.copy()
e["a"] = (0, 0)
print(d["a"], e["a"], dict(d) == d, d == e, d == {**d})

# reads
print(d["a"], d["a"][0] - 1, d["c"], d["c"][0] == EDGE)
x, y = d["d"]
print(x // BIG, y)
for k, v in d.items():
    print(k, v, v[0] + v[1])
for v in d.values():
    print(v[0] - 1)
print(sorted(d.values()), max(d.values()), min(d.values()))
print(list(d.values()), sorted(d.items()), (5, BIG) in d.values(), (5, BIG + 1) in d.values())
print(list(d.items())[0], [v for v in d.values() if v[0] > 2 ** 63])
k, v = d.popitem()
print(k, v, v[0] - 1)
print(repr(d), d != c, d.get("b", (0, 0)) == (5, BIG))

# nested tuples, tuples of an int and a str, int keys
n: dict[int, tuple[tuple[int, int], str]] = {1: ((BIG, 2), "x"), 2: ((EDGE, 3), "y")}
print(n, n[1][0][0] - 1, sorted(n.values()), list(n.items()))
s = {"p": (BIG, "q")}
s["r"] = (EDGE, "t")
print(s, s["p"][0] + 1, max(s.values()))
ik = {BIG: (BIG, 1), 2: (3, 4)}
ik[EDGE] = (EDGE, BIG)
print(ik, ik[BIG], ik.get(2), ik.get(99), list(ik.items()), sorted(ik.items()))
print(ik.popitem(), ik.popitem())

# a module that does not opt in
v1 = {"a": (1, 2), "z": (BIG, 1)}
print(first_value(v1))
put(v1, "w", 3, 4)
print(v1, total({"q": (1, 2)}))
m = made()
print(m, m["m"][0] - 1, m["n"][1] + 1)
m["o"] = edge()
print(m["o"], m["o"][0] - 1, sorted(m.values()))
