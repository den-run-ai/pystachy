# objects of classes that define __hash__ and __eq__ as dict keys and set elements: CPython calls
# __hash__ once for each insertion or lookup (a set or dict made of another's keys takes their
# hashes), and __eq__ for each key of the same hash that the probes meet, stored key first; a
# set of them iterates in CPython's order, which their hashes decide


log: list[str] = []


def flush(label: str) -> None:
    print(label, log)
    log.clear()


class P:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def __eq__(self, other: "P") -> bool:
        log.append(f"eq {self.x},{self.y} {other.x},{other.y}")
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        log.append(f"hash {self.x},{self.y}")
        return self.x * 31 + self.y

    def __repr__(self) -> str:
        return f"P({self.x}, {self.y})"


d: dict[P, str] = {}
d[P(1, 2)] = "a"
flush("set")
d[P(1, 2)] = "b"
flush("overwrite")
print(d, P(1, 2) in d, P(2, 1) in d)
flush("in")
print(d[P(1, 2)], d.get(P(9, 9)), d.get(P(1, 2), "z"))
flush("getitem, get")
try:
    print(d[P(3, 3)])
except KeyError as e:
    print("KeyError", e)
flush("missing")
del d[P(1, 2)]
flush("del")
print(d)
s = {P(0, 31), P(1, 0), P(0, 31)}
flush("display")
print(len(s), s)
s.add(P(1, 0))
flush("add")
print(P(0, 31) in s)
flush("in set")
s.discard(P(0, 31))
flush("discard")
print(s, {P(1, 0)} | s)
flush("or")
h = {P(i, i) for i in range(5)}
flush("comprehension")
print(h, list(h))
c: dict[P, int] = {}
for p in [P(1, 1), P(1, 1), P(2, 2)]:
    c[p] = c.get(p, 0) + 1
flush("count")
c[P(1, 1)] += 5
flush("augmented")
print(c)
if P(2, 2) in c:
    print(c[P(2, 2)])
flush("in, then getitem")
print(c.setdefault(P(3, 3), 0), c.setdefault(P(3, 3), 1))
flush("setdefault")
print(c.pop(P(3, 3)), c.pop(P(4, 4), -1))
flush("pop")
print(set([P(5, 5), P(5, 5)]), dict.fromkeys([P(6, 6), P(6, 6)], 0))
flush("set(list), fromkeys")
k = {(P(1, 1), 2): 3}
flush("tuple key")
print(k[(P(1, 1), 2)], (P(1, 1), 3) in k)
flush("tuple getitem")


class K:
    # hashes that collide (v % 4), an __eq__ for other types, and a hash that raises
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, K):
            return False
        log.append(f"eq {self.v} {other.v}")
        return self.v == other.v

    def __hash__(self) -> int:
        log.append(f"hash {self.v}")
        if self.v < 0:
            raise ValueError(f"bad key {self.v}")
        return self.v % 4

    def __repr__(self) -> str:
        return f"K{self.v}"


ks = [K(i) for i in range(6)]
kd: dict[K, int] = {}
for x in ks:
    kd[x] = x.v
flush("insert")
ss = set(kd)
flush("set(d)")
print(ss, sorted([x.v for x in ss]))
print(len(ss.difference({ks[0]: 0})), len(ss - {ks[1]}))
flush("difference")
u = set(ks[:3])
u.update({ks[4]: 1})
flush("update(d)")
u.symmetric_difference_update({ks[4]: 1, ks[5]: 2})
flush("^= d")
print(sorted([x.v for x in u]))
e = dict(kd)
flush("dict(d)")
print(e == kd, e != kd)
flush("==")
e[ks[1]] = 99
print(e == kd, kd == {K(0): 0})
flush("== differs")
f = kd.copy()
f.update(e)
flush("copy, update")
print(K(1) == 1, ks[2] in [K(2)], ks[2] in {K(2)})
flush("other types")
try:
    kd[K(-1)] = 1
except ValueError as x:
    print("ValueError", x)
flush("raising __hash__")
try:
    print(K(-2) in ss)
except ValueError as x:
    print("ValueError", x)
try:
    print({(1, K(-3)): 0})
except ValueError as x:
    print("ValueError", x)
flush("raising __hash__ in a set, a tuple")
print(len(kd), len(ss))


class Mut:
    # an __eq__ that empties the dict it compares in: the lookup starts again, as in CPython
    def __init__(self, v: int, box: dict["Mut", int]) -> None:
        self.v = v
        self.box = box

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mut):
            return False
        if self.v == 0:
            self.box.clear()
            log.append("cleared")
        return self.v == other.v

    def __hash__(self) -> int:
        return 7


box: dict[Mut, int] = {}
box[Mut(0, box)] = 1
box[Mut(1, box)] = 2
flush("mutating __eq__")
box[Mut(2, box)] = 3
print(len(box), [m.v for m in box])


class Neg:
    # __hash__ results: -1 is -2, a bool is an int, a large int is itself
    def __init__(self, h: int) -> None:
        self.h = h

    def __hash__(self) -> int:
        return self.h


class Flag:
    def __hash__(self) -> bool:
        return True


print(hash(Neg(-1)), hash(Neg(-2)), hash(Neg(2**62)), hash(Neg(0)), hash(Flag()))
n1 = Neg(-1)
print({n1: 1}[n1], Neg(5) in {Neg(5)}, len({Neg(-1), Neg(-2), Neg(-1)}))
