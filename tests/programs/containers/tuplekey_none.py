# Tuple keys and items that hold None: a None item takes its type from the other items of a
# display (and is a str | None where nothing gives it one), a tuple whose item may be None is
# looked up among keys whose items cannot be (it is in none of them), a bool is looked up as
# the int it equals, and dicts whose tuple keys differ in what may be None compare.
import sys

print({("a", None): 1, ("b", "c"): 2}, {("b", "c"): 2, ("a", None): 1})
print([("a", None), ("b", "c")], {1: ("a", None), 2: ("b", "c")}, {(1, None): "x"})
d = {(1, None): 1} if len(sys.argv) > 5 else {(1, "x"): 1}
print(d)

e = {}
e["a", None] = 1
e["b", "c"] = 2
e["a", None] += 5
print(e, ("a", None) in e, e.get(("b", "c"), 0), e[("b", "c")])


def count(xs):
    d = {}
    for x in xs:
        d[x] = d.get(x, 0) + 1
    return d


print(count([(True, None), (False, None), (True, None)]))

a: dict[tuple[str | None, int], int] = {("a", 1): 1}
b: dict[tuple[str, int], int] = {("a", 1): 1}
print(a == b, b == a, a != b)
a[None, 2] = 2
print(a == b, b == a, a)

x: str | None = None
print((x, 1) in b, b.get((x, 1), -1), b.pop((x, 1), -2), (None, 1) in b)
x = "a"
print((x, 1) in b, b.get((x, 1), -1), b[x, 1])
s = {("a", "b"): 1}
print(("a", None) in s, s.get(("a", None), 0), [("a", None)] == [("a", "b")])

n = {(1, 2): "a", (0, 3): "b"}
print(n[True, 2], (True, 2) in n, (False, 3) in n, n.get((True, 3), "-"), True in {1: "x"}, {1: "x"}[True])
print(n.pop((False, 3)), n)

t: dict[tuple[()], int] = {}
t[()] = 1
print(t, () in t)

y: str | None = None
print(b[y, 1])
