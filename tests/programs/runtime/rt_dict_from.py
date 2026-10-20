# dict(d) merges d into a new empty dict, as CPython does: the copy clones d's table only when
# that has no holes and is not sparse, and is otherwise a compact table sized for the items;
# d.copy() clones whenever at most a third of the entries are holes. Which table a copy has
# decides what a loop that changes it sees.


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


def walk_del(e: dict[int, int], cap: int, off: int) -> None:
    # deleting first: an insertion into the full table then rebuilds it without that hole
    n = 0
    for k in e:
        n += 1
        if n > cap:
            break
        print(k, end=" ")
        del e[k]
        e[k + off] = n
    print(e)


d = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9}
del d[3]
walk(dict(d), 7, 10)
walk(d.copy(), 7, 10)

d = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9}
del d[4]
del d[9]
del d[0]
walk(dict(d), 5, 100)
walk(d.copy(), 5, 100)

d = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9}
del d[1]
del d[5]
del d[0]
walk(dict(d), 4, 10)
walk(d.copy(), 4, 10)

# no holes, but sparse: 21 keys, 17 deleted, then an insertion rebuilds the table at 16 slots for 5
s: dict[int, int] = {}
for i in range(21):
    s[i] = i
for i in range(17):
    del s[i]
s[30] = 30
walk_del(dict(s), 3, 5)
walk_del(s.copy(), 3, 5)

# no holes and not sparse: both clone
c = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7}
walk(dict(c), 7, 20)
walk(c.copy(), 7, 20)

# empty sources, and str keys
z: dict[int, int] = {}
print(dict(z), z.copy())
for i in range(3):
    z[i] = i
for i in range(3):
    del z[i]
y = dict(z)
y[5] = 5
print(y, dict(z))
t = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6, "g": 7}
del t["b"]
u = dict(t)
n = 0
for k in u:
    n += 1
    if n > 5:
        break
    print(k, end=" ")
    u[k + "x"] = n
    del u[k]
print(u, t)
