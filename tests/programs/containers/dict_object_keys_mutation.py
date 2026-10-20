# keys whose __eq__ or __repr__ empties the dict or set it is compared or printed in: printing,
# equality, lookups and the set operations go on with what is left (a lookup starts again, as
# CPython's does), and read nothing that the change freed; and keys whose __eq__ inserts into it


log: list[str] = []


class K:
    def __init__(self, v: int) -> None:
        self.v = v
        self.victims: list[dict["K", int]] = []
        self.svictims: list[set["K"]] = []

    def __hash__(self) -> int:
        return 1

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, K):
            return False
        log.append(f"eq {self.v} {other.v}")
        for d in self.victims:
            d.clear()
        for s in self.svictims:
            s.clear()
        self.victims = []
        self.svictims = []
        return self.v == other.v

    def __repr__(self) -> str:
        for d in self.victims:
            d.clear()
        self.victims = []
        return f"K{self.v}"


def flush(label: str) -> None:
    print(label, log)
    log.clear()


a = K(1)
b = K(2)
d = {a: 1, b: 2}
flush("built")
a.victims = [d]
print(d, d)
x = {K(1): 1, K(2): 2}
y = {K(1): 1, K(2): 2}
flush("built")
for k in x:
    k.victims = [x]
print(x == y, x, y)
flush("==")
s = {K(1), K(2), K(3)}
t = {K(1), K(2), K(3)}
flush("built")
for k in t:
    k.svictims = [t]
r = s - t
print(r, len(t))
flush("-")
t = {K(1), K(2), K(3)}
for k in t:
    k.svictims = [t]
print(s & t, len(t))
flush("&")
t = {K(1), K(2), K(3)}
for k in t:
    k.svictims = [t]
print(len(s ^ t), len(t))
flush("^")
u = {K(1), K(2)}
w: dict[K, int] = {}
for k in u:
    w[K(k.v)] = 0
for k in w:
    k.svictims = [u]
flush("built")
print(u.difference(w), len(u))
flush("difference(d)")
v = {K(1), K(2), K(3)}
z = {K(1)}
for k in v:
    k.svictims = [v]
print(K(2) in v, len(v), z <= v, v.isdisjoint(z))
flush("in, <=, isdisjoint")


class Filler:
    # a key whose __eq__ inserts another key into the dict it is compared in, once
    def __init__(self, name: str, into: dict["Filler", int] | None) -> None:
        self.name = name
        self.into = into

    def __hash__(self) -> int:
        return 5

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Filler):
            return False
        into = self.into
        if into is not None:
            self.into = None
            into[Filler("z", None)] = 99
        return self.name == other.name

    def __repr__(self) -> str:
        return self.name


# d[k] = v whose lookup passed the hole of a deleted key, where the __eq__ it ran inserted
# another key: k goes where the table has room after the lookup (CPython's find_empty_slot)
f: dict[Filler, int] = {}
for i, nm in enumerate(["a", "b", "c"]):
    f[Filler(nm, None)] = i
del f[Filler("a", None)]
for fk in f:
    if fk.name == "c":
        fk.into = f
f[Filler("n", None)] = 4
print(f, len(f), [f[fk] for fk in list(f)])
print(Filler("z", None) in f, Filler("n", None) in f, Filler("b", None) in f)


class TK:
    # an item of tuple keys whose __eq__ inserts a key into the dict and the set it is compared in
    tlog: list[str] = []
    victim: dict[tuple[int, "TK"], int] = {}
    svictim: set[tuple[int, "TK"]] = set()

    def __init__(self, v: int, mutate: bool) -> None:
        self.v = v
        self.mutate = mutate

    def __eq__(self, other: "TK") -> bool:
        TK.tlog.append(f"eq {self.v} {other.v}")
        if self.mutate or other.mutate:
            self.mutate = False
            other.mutate = False
            TK.victim[(9, TK(9, False))] = 9
            TK.svictim.add((9, TK(9, False)))
        return self.v == other.v

    def __hash__(self) -> int:
        TK.tlog.append(f"hash {self.v}")
        return 7


# tuple keys of equal hashes: a lookup compares their items in order, an object's by its __eq__,
# meets a key again where CPython's probes visit its slot again, and goes on after an insertion
ta = TK(1, False)
tb = TK(2, True)
TK.victim[(1, ta)] = 1
TK.victim[(2, tb)] = 2
print((2, TK(2, False)) in TK.victim, len(TK.victim))
print((1, TK(3, False)) in TK.victim)
TK.svictim.add((1, ta))
TK.svictim.add((2, tb))
tb.mutate = True
print((2, TK(2, False)) in TK.svictim, len(TK.svictim))
print((0, TK(2, False)) in TK.svictim)
td: dict[tuple[int, tuple[str, TK] | None], int] = {(1, ("x", ta)): 1, (2, None): 2}
print(td[(1, ("x", TK(1, False)))], td[(2, None)])
print(TK.tlog)
