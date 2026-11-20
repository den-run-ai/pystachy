# a key whose __eq__ removes the entry that a lookup is comparing and stores its key again
# (popitem(), then d[x] = v): the key keeps its entry and takes another index slot, the first
# hole of its probes. The lookup goes on with that entry, as CPython's does, and calls __eq__
# once: a store, a read, in, del, pop, get and setdefault through an equal key leave the strs
# allocated beside the dict as they were (#1580). Where that __eq__ answers False the probes go
# on, and where it only removes the entry the lookup starts again; so does one that removes a
# None key, whose word is a hole's


class K:
    def __init__(self, h: int, name: str) -> None:
        self.h = h
        self.name = name

    def __hash__(self) -> int:
        return self.h

    def __eq__(self, other: object) -> bool:
        global armed, calls
        calls += 1
        if armed != "":
            how = armed
            armed = ""
            if how == "none":
                dn.popitem()
                return True
            d.popitem()
            if how != "gone":
                d[x] = 99
            if how == "unequal":
                return False
        return isinstance(other, K) and other.h == self.h

    def __repr__(self) -> str:
        return self.name


armed = ""
calls = 0
strs: list[str] = []
d: dict[K, int] = {}
dn: dict[K | None, int] = {}
x = K(32, "x")


def table() -> None:
    # y and x share the first slot of their probes: x, stored second, takes a later one, and
    # deleting y leaves a hole before it. The strs are made first, beside the dict's arrays
    global d, x, strs, calls
    strs = ["-" * (16 + i) for i in range(8)]
    d = {}
    y = K(64, "y")
    x = K(32, "x")
    d[y] = 1
    d[x] = 2
    del d[y]
    calls = 0


def run(op: str, how: str) -> None:
    global armed
    table()
    k = K(32, "k")
    armed = how
    try:
        if op == "set":
            d[k] = 0x4141414141414141
        elif op == "get":
            print(d[k])
        elif op == "in":
            print(k in d)
        elif op == "del":
            del d[k]
        elif op == "pop":
            print(d.pop(k))
        elif op == "popdefault":
            print(d.pop(k, -1))
        elif op == "getdefault":
            print(d.get(k, -1))
        elif op == "setdefault":
            print(d.setdefault(k, 5))
        elif op == "iadd":
            d[k] += 1
    except KeyError as e:
        print("KeyError", e)
    print(op, how, d, len(d), list(d.values()), calls, all([s == "-" * len(s) for s in strs]))


for how in ["moved", "unequal", "gone"]:
    for op in ["set", "get", "in", "del", "pop", "popdefault", "getdefault", "setdefault", "iadd"]:
        run(op, how)

# a None key, which a lookup of an object of its hash compares by that object's __eq__
none_hash = hash(None)
for op in ["set", "get", "in", "pop"]:
    dn = {None: 1}
    kn = K(none_hash, "kn")
    calls = 0
    armed = "none"
    if op == "set":
        dn[kn] = 7
    elif op == "get":
        print(dn.get(kn, -1))
    elif op == "in":
        print(kn in dn)
    else:
        print(dn.pop(kn, -1))
    print(op, dn, len(dn), calls)
