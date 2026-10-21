# d.update(): a dict of d's type, a list of (key, value) pairs and keyword arguments. A key d
# holds keeps its place and takes the new value; a new one goes at the end. A dict is merged as
# CPython merges one: into an empty d as a clone of its table where dict(o) would clone it, else
# into d resized once for both dicts' items when o has more than d's table could take; which
# table d ends with decides what a loop that changes it sees (walk).


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


d = {"a": 1, "b": 2, "c": 3}
d.update({"b": 20, "d": 4})
print(d)
d.update([("e", 5), ("a", 10), ("e", 50)])
print(d)
d.update(f=6, a=100)
print(d)
print(d.update({"g": 7}, h=8, b=-2), d)
d.update()
d.update(d)
d.update({})
d.update([])
print(d)
del d["a"]
d.update(a=0)
print(d)
d.update(d.items())
print(d, len(d))

# the arguments are evaluated first, then merged in order: the dict, then the keywords
log: list[str] = []


def val(s: str, v: int) -> int:
    log.append(s)
    return v


src = {"x": 1}
d.update(src, x=val("kw", 2), y=val("kw2", len(src)))
print(d["x"], d["y"], log)

# other key and value types
t: dict[tuple[int, str], list[int]] = {(1, "a"): [1]}
t.update({(2, "b"): [2], (1, "a"): []})
t.update([((3, "c"), [3, 3])])
print(t)
o: dict[str, int | None] = {"a": None}
o.update(a=1, b=None)
o.update({"c": 2}, d=None)
print(o)

# into an empty dict: a clone of a table without holes (both loops see the same table), but a
# compact table sized for the items where o has holes or is sparse
c = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7}
e: dict[int, int] = {}
e.update(c)
walk(e, 7, 20)
walk(dict(c), 7, 20)
c = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9}
del c[3]
e = {}
e.update(c)
walk(e, 7, 10)
e = {0: 0}
del e[0]
e.update(c)
walk(e, 7, 10)
# an empty dict whose table is still there (its items deleted) takes the clone all the same
e = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}
for k in range(7):
    del e[k]
e.update({0: 0, 1: 1, 2: 2})
walk(e, 2, 20)

# resized once, before the items go in, for both dicts' items (the keys they share counted
# twice) when o has more than d's table could take; a list of pairs grows the table as it fills
r = {0: 0, 1: 1, 2: 2}
r.update({0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7})
walk(r, 7, 5000)
r = {0: 0, 1: 1, 2: 2}
r.update([(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7)])
walk(r, 7, 5000)

# an update of the keys a loop's dict holds changes no size; a new key does
w = {1: 1, 2: 2}
for k in w:
    w.update({k: k * 10})
print(w)
try:
    for k in w:
        w.update([(k + 1, 0)])
except RuntimeError as x:
    print("RuntimeError:", x, w)

# None is not iterable
m: dict[str, int] | None = None
try:
    d.update(m, z=val("before the TypeError", 0))
except TypeError as x:
    print("TypeError:", x, log[-1], "z" in d)
