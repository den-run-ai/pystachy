# Loops over lists whose bodies change the list they read (listget, docs/typed-ir.md 7.1: each
# item is read without a bounds check, right after the loop tests its index against the list's
# current length). Run with PYSTACHY_OPT=-listget too.


class Bag:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def drop(self) -> None:
        if len(self.xs) > 0:
            self.xs.pop()

    def add(self, x: int) -> None:
        self.xs.append(x)


G: list[int] = [1, 2, 3, 4, 5, 6]


def shrink_global() -> None:
    del G[0]


def grows() -> None:
    xs = [1, 2]
    for x in xs:
        if x < 6:
            xs.append(x + 2)
        print(x, end=" ")
    print(xs)


def pops() -> None:
    xs = [1, 2, 3, 4, 5, 6, 7]
    for x in xs:
        xs.pop()
        print(x, len(xs), end="; ")
    print(xs)
    ys = [9, 8, 7, 6]
    for y in ys:
        ys.pop(0)
        print(y, end=" ")
    print(ys)


def deletes() -> None:
    xs = [10, 20, 30, 40, 50]
    for x in xs:
        del xs[0]
        print(x, end=" ")
    print(xs)
    zs = [1, 2, 3, 4]
    for z in zs:
        if z == 2:
            zs.clear()
        print(z, end=" ")
    print(zs)
    ws = [5, 6, 7]
    for w in ws:
        while len(ws) > 1:
            del ws[len(ws) - 1]
        ws.insert(0, w * 10)
        print(w, ws, end=" ")
        if len(ws) > 4:
            break
    print()


def through_methods() -> None:
    b = Bag([1, 2, 3, 4, 5])
    for x in b.xs:
        b.drop()  # a method call that shortens the list being read
        print(x, end=" ")
    print(b.xs)
    c = Bag([1])
    for x in c.xs:
        if x < 4:
            c.add(x + 1)  # and one that grows it
        print(x, end=" ")
    print(c.xs)
    for g in G:
        shrink_global()  # a function that changes a global list
        print(g, G, end=" ")
    print()


def aliases() -> None:
    xs = [1, 2, 3, 4, 5]
    ys = xs
    for x in xs:
        ys.pop()  # the same list through another variable
        print(x, end=" ")
    print(xs, ys)
    xs = [1, 2, 3]
    for x in xs:
        xs = [7, 8, 9, 10]  # the loop keeps the list it started with
        print(x, end=" ")
    print(xs)
    nest = [[1, 2], [3, 4, 5]]
    inner = nest[1]
    for row in nest:
        for v in row:
            inner.pop()
            print(v, end=" ")
    print(nest)


def pairs() -> None:
    xs = [1, 2, 3, 4, 5, 6]
    for a, b in zip(xs, xs):
        xs.pop()
        print(a + b, end=" ")
    print(xs)
    ys = [1, 2, 3, 4]
    zs = [5, 6, 7, 8, 9]
    for a, b in zip(ys, zs):
        zs.pop(0)
        print(a, b, end="; ")
    print(zs)
    es = ["a", "b", "c", "d"]
    for i, e in enumerate(es, 10):
        if i == 11:
            es.pop()
        print(i, e, end=" ")
    print(es)


def backwards() -> None:
    xs = [1, 2, 3, 4, 5]
    for x in reversed(xs):
        xs.pop()
        xs.pop()
        print(x, xs, end=" ")
    print()
    ys = [1, 2, 3]
    for y in reversed(ys):
        ys.insert(0, y * 10)  # the items move: reversed reads by index, as CPython's iterator does
        print(y, end=" ")
    print(ys)
    zs = [1, 2, 3, 4]
    for z in reversed(zs):
        zs.clear()
        print(z, end=" ")
    print(zs)


def kinds() -> None:
    fs = [0.5, 1.5, 2.5]
    for f in fs:
        if f < 2.0:
            fs.append(f * 3)
        print(f, end=" ")
    print()
    bs = [True, False, True]
    for b in bs:
        if b and True in bs:
            bs.remove(True)
        print(b, end=" ")
    print(bs)
    ss = ["x", "yy", "zzz"]
    for s in ss:
        ss[len(ss) - 1] = s.upper()
        print(s, end=" ")
    print(ss)
    ts = [(1, "a"), (2, "b")]
    for t in ts:
        if t[0] == 1:
            ts.append((3, "c"))
        print(t, end=" ")
    print()
    objs = [Bag([1]), Bag([2, 3])]
    for o in objs:
        objs.pop()
        print(o.xs, end=" ")
    print(len(objs))
    names = ["", "", "q"]
    print(any(names), all(names), all(["a", "b"]))


grows()
pops()
deletes()
through_methods()
aliases()
pairs()
backwards()
kinds()
