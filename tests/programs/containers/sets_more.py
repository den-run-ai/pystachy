# sets: update() with several arguments, each evaluated first and then added in turn (a
# generator's elements as it yields them); hasattr(); how an empty set() gets its type
def noisy(tag: str, v: int) -> int:
    print("eval", tag, v)
    return v


u = {1}
u.update([noisy("a", 5)], (noisy("g", x) for x in [7, 8]), [noisy("b", len(u))])
print(u)
w = {1}
try:
    w.update((x + 1 for x in w), [3])
except RuntimeError as e:
    print("RuntimeError", e)
print(w)
v = {10}
try:
    v.update([20], (100 // x for x in [5, 0, 1]))
except ZeroDivisionError as e:
    print("ZeroDivisionError", e)
print(v)

# an empty set() takes the type the first argument of its first update() shows
s = set()
s.update([1], [2])
print(s)
t = set()
print(len(t))
t.update([3], (x * 2 for x in range(3)), {9})
print(t)
m = set()
m.update(map(lambda x: x + 1, [1, 2]), [noisy("c", 0)])
print(m)
q = set()
q.update((noisy("h", x) for x in [4]), [noisy("d", 6)], map(len, ["ab"]))
print(q)

f = frozenset({1, 2})
print(hasattr({1}, "add"), hasattr(f, "add"), hasattr(f, "union"), hasattr({1}, "__iand__"), hasattr({1}, "sort"), hasattr(f, "__isub__"))


# a template's set that its argument types leave empty, as a list is: returned as it is, or an
# empty set of ints where it is read
def keep(x):
    s = set()
    if isinstance(x, str):
        s.add(x)
    return s


def count(x):
    s = set()
    if isinstance(x, str):
        s.update([x, x])
    print(len(s), bool(s), s)


print(keep(1), keep("a"))
r: set[str] = keep(2)
print(r, len(keep(3)))
count(1)
count("b")
