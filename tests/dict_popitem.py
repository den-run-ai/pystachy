# d.popitem() removes and returns the last pair d holds, in the order a loop sees them (after del
# and re-insertion too). The next insertion takes the popped entry's place, but popitem() gives
# the table no room back (as in CPython), so an insertion after popitems may rebuild it, which
# decides what a loop that changes the dict sees (walk).


def walk(e: dict[int, int], cap: int, off: int) -> None:
    n = 0
    for k in e:
        n += 1
        if n > cap:
            break
        print(k, end=" ")
        e[k + off] = n
        del e[k]
    print(e)


d = {"a": 1, "b": 2, "c": 3, "d": 4}
print(d.popitem(), d)
del d["a"]
d["a"] = 10
d["e"] = 5
print(d.popitem(), d.popitem(), d)
k, v = d.popitem()
print(k, v, d, len(d))
d["c"] = 30
print(d)
t = {(1, "x"): [1], (2, "y"): [2, 2]}
print(t.popitem(), t)
while d:
    print(d.popitem(), end=" ")
print(d, len(d))

# the empty dict's KeyError
e: dict[int, str] = {}
try:
    e.popitem()
except KeyError as x:
    print("KeyError:", x, repr(x))
e[1] = "one"
print(e.popitem(), e)

# a full table: after two popitems, as after two dels, an insertion rebuilds it (16 slots), where
# a table that took its room back would still have 8
p = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}
print(p.popitem(), p.popitem())
p[10] = 10
walk(p, 3, 20)
q = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}
del q[4]
del q[3]
q[10] = 10
walk(q, 3, 20)

# a popitem in a loop over the dict changes its size
s = {1: 1, 2: 2, 3: 3}
try:
    for j in s:
        print(j, s.popitem())
except RuntimeError as x:
    print("RuntimeError:", x, s)

# an optional dict that is None
o: dict[str, int] | None = None
if len(s) > 0:
    o = None
try:
    o.popitem()
except AttributeError as x:
    print("AttributeError:", x)
