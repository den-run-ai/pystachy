# dict.popitem() of dicts whose keys are objects: hashed by their class's __hash__ (the table's
# index has CPython's size slots, and a hash may be 0), by identity, and tuples holding them;
# popitem() runs neither __hash__ nor __eq__, and inserts after pops rebuild the table where
# CPython's does


log: list[str] = []


class K:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: "K") -> bool:
        log.append(f"eq {self.n} {other.n}")
        return self.n == other.n

    def __hash__(self) -> int:
        log.append(f"hash {self.n}")
        return self.n % 4 - 1   # 0, -1 (which hashes as -2) and collisions

    def __repr__(self) -> str:
        return f"K({self.n})"


class Plain:
    def __init__(self, n: int) -> None:
        self.n = n

    def __repr__(self) -> str:
        return f"Plain({self.n})"


d: dict[K, int] = {}
for i in range(12):
    d[K(i)] = i
log.clear()
print(d.popitem(), d.popitem(), len(d), log)
while d:
    k, v = d.popitem()
    print(k, v, end="; ")
print(d, log)
z: dict[K, str] = {K(1): "a", K(5): "b", K(9): "c"}   # all hash to 0
print(z.popitem(), z, K(1) in z, K(9) in z)
log.clear()

# popitem() and inserts in turn: the cut-off entries still fill the table
c: dict[K, int] = {K(0): 0}
for j in range(1, 300):
    c.popitem()
    c[K(j)] = j
log.clear()
print(c, K(299) in c, K(298) in c, c.copy(), dict(c))
log.clear()
for size in range(1, 10):
    t: dict[K, int] = {}
    for j in range(size):
        t[K(j)] = j
    for j in range(size):
        t.popitem()
        t[K(100 + j)] = j
    seen: list[int] = []
    try:
        for k4 in t:
            seen.append(k4.n)
            del t[k4]
            t[K(k4.n + 1000)] = k4.n
    except RuntimeError as e:
        print(size, "RuntimeError", e, seen)
    else:
        print(size, seen, sorted([k5.n for k5 in t]))
log.clear()

# identity-hashed objects, and tuples holding hashed objects
p: dict[Plain, int] = {}
objs = [Plain(i) for i in range(20)]
for i in range(20):
    p[objs[i]] = i
for i in range(5):
    print(p.popitem(), end=" ")
print(len(p), objs[3] in p, objs[17] in p)
for j in range(200):
    p.popitem()
    p[objs[j % 20]] = j
print(len(p))
tk: dict[tuple[K, int], str] = {}
for i in range(10):
    tk[(K(i), i)] = str(i)
print(tk.popitem(), tk.popitem(), len(tk))
for j in range(100):
    tk.popitem()
    tk[(K(j), -j)] = "x"
print(len(tk), (K(99), -99) in tk)
log.clear()
e: dict[K, int] = {}
try:
    e.popitem()
except KeyError as ex:
    print("KeyError", ex, log)
