# set[None] and frozenset[None]: None is an element like any other (mypyc's selfleaks analysis
# keeps its dataflow facts in such sets)
def show(tag: str, s: set[None]) -> None:
    print(tag, len(s), bool(s), None in s, None not in s, s)


def empty() -> set[None]:
    return set()


s: set[None] = {None}
show("display", s)
t: set[None] = set()
show("empty", t)
t.add(None)
t.add(None)
show("added", t)
t.discard(None)
show("discarded", t)
t.discard(None)
t.add(None)
t.remove(None)
show("removed", t)
try:
    t.remove(None)
except KeyError as e:
    print("KeyError", e)
t |= s
show("ior", t)
print(t == s, t != s, t <= s, t < s, t >= s, t.issubset(s), t.isdisjoint(s), t.isdisjoint(empty()))
t -= s
show("isub", t)
print(t == s, t <= s, t < s, s > t)
u = s | t
v = s & t
w = s - t
x = s ^ s
show("or", u)
show("and", v)
show("sub", w)
show("xor", x)
c = s.copy()
c.clear()
show("copy cleared", c)
show("source", s)
for item in s:
    print("item", item, item is None)
print([item for item in s], len([item for item in s]))
print(s.pop(), len(s))
try:
    s.pop()
except KeyError as e:
    print("KeyError", e)
s.update(u)
s.update([None, None])
show("updated", s)
s.difference_update(u)
show("difference_update", s)
s.symmetric_difference_update(u)
show("symmetric_difference_update", s)
s.intersection_update(u)
show("intersection_update", s)
print(s.union(u), s.intersection(u), s.difference(u), s.symmetric_difference(u))
print(s.issuperset(u), s.issubset(t))
f: frozenset[None] = frozenset({None})
g: frozenset[None] = frozenset()
print(f, g, len(f), None in f, None in g, f == s, g == s, f | g, f & g, f - g, g - f)
h = {None}
h.add(None)
print(h, len(h), type(h).__name__)
i = frozenset([None, None])
print(i, len(i))
print({n for n in (None, None)}, {n for n in h})
