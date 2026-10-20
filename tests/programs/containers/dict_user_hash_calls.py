# when a dict of keys hashed by their class runs their __hash__ and __eq__, as CPython's does: a
# lookup finds a key as itself before it compares hashes (a key whose hash changed since it was
# inserted is found where the probes of its new hash meet it; a set compares hashes first);
# d.pop(k) and d.pop(k, default) of an empty dict do not hash k, del d[k] does; dict(d) and
# d.copy() of a dict with many deleted keys insert its keys one by one, which compares those of
# one hash, and copy the table of a dict with few


log: list[str] = []


class M:
    def __init__(self, name: str, h: int) -> None:
        self.name = name
        self.h = h

    def __hash__(self) -> int:
        log.append(f"hash {self.name}")
        return self.h

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, M):
            return False
        log.append(f"{self.name}={other.name}")
        return self.name == other.name

    def __repr__(self) -> str:
        return f"M({self.name})"


def flush(label: str) -> None:
    print(label, log)
    log.clear()


# a key whose hash changes after its insertion: 1, then 9, which starts at the same slot of an
# 8-slot table, then 2, which does not
m = M("m", 1)
d = {m: 1}
s = {m}
m.h = 9
print(m in d, d[m], d.get(m), m in s)
d[m] = 2
print(len(d), d)
m.h = 2
print(m in d, d.get(m, -1), m in s)
m.h = 9
del d[m]
print(len(d), m in d)
flush("changed hash")
# ... behind a key of its new hash, whose __eq__ runs first
a = M("a", 9)
m = M("m", 1)
d = {a: 1, m: 2}
m.h = 9
print(m in d, d[m], d.pop(m), len(d))
flush("behind a")
big: dict[M, int] = {}
ms = [M(f"k{i}", i) for i in range(40)]
for i, k in enumerate(ms):
    big[k] = i
for k in ms:
    k.h += 64
print(sum([big[k] for k in ms]), len([k for k in ms if k in big]))
log.clear()

# pop of an empty dict, also one emptied by deletions: no __hash__; del hashes the key
e: dict[M, int] = {}
for label in ["new", "emptied"]:
    if label == "emptied":
        e[M("x", 3)] = 1
        e.pop(M("x", 3))
        log.clear()
    try:
        e.pop(M("k", 1))
    except KeyError as x:
        print("KeyError", x)
    print(e.pop(M("k", 1), 5), e.pop(M("k", 1), None))
    flush(f"pop {label}")
    try:
        del e[M("k", 1)]
    except KeyError as x:
        print("KeyError", x)
    flush(f"del {label}")
f = {M("a", 1): 1.5}
print(f.pop(M("b", 1), None), f.pop(M("a", 1), None), f.pop(M("a", 1), None))
flush("pop float")

# copies: keys of hash 4 (and 5), most of them deleted
for n, step in [(10, 2), (10, 3), (12, 4), (6, 6)]:
    d = {}
    keys = [M(f"k{i}", 4 + i % 2) for i in range(n)]
    for i, k in enumerate(keys):
        d[k] = i
    for i in range(0, n, step):
        del d[keys[i]]
    log.clear()
    c = d.copy()
    flush(f"copy {n} {step}")
    c2 = dict(d)
    flush(f"dict {n} {step}")
    print(c == d, c2 == c, list(c2))
    log.clear()
    c[M("new", 4)] = -1
    c2[M("new", 4)] = -1
    flush("insert")
    print(len(c), len(c2), list(c)[-2:])
    log.clear()
# a dict without deleted keys: its table is copied, comparing nothing
d = {M("p", 4): 1, M("q", 4): 2, M("r", 4): 3}
log.clear()
c = d.copy()
c2 = dict(d)
flush("clean")
print(c, c2)
log.clear()
# an __eq__ that is True for two of the keys it is asked about: a copy keeps the first with the
# second's value, as CPython's insertion does
flaky = False


class F:
    def __init__(self, name: str) -> None:
        self.name = name

    def __hash__(self) -> int:
        return 7

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, F):
            return False
        return flaky or self.name == other.name

    def __repr__(self) -> str:
        return self.name


fd = {F("a"): 1, F("b"): 2, F("c"): 3, F("d"): 4, F("e"): 5, F("f"): 6}
for nm in "abc":
    del fd[F(nm)]
flaky = True
print(fd.copy(), dict(fd), len(fd))
