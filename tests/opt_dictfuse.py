# Dict lookups that dictfuse (docs/typed-ir.md 7.1) makes one: a has or a getitem of a key, then
# a getitem or a set of it, share the entry the first finds while no dict changes between. Here
# the code between changes the dict, directly, through a function or a method, or through
# another variable, so the entry must be looked up again; and a getitem that fails raises
# CPython's KeyError. Run with PYSTACHY_OPT=-dictfuse too.


class Counter:
    def __init__(self) -> None:
        self.d: dict[str, int] = {}
        self.n = 0

    def add(self, k: str) -> None:
        if k in self.d:
            self.n += 1  # a field store between the has and the getitem and set
            self.d[k] += 1
        else:
            self.d[k] = 1

    def reset(self) -> None:
        self.d = {"x": 100, "p": 50}

    def bump_after_reset(self, k: str) -> None:
        if k in self.d:
            self.reset()  # self.d is another dict now
            self.d[k] = self.d[k] + 1


G: dict[int, int] = {1: 10, 2: 20}


def clear_global() -> None:
    G.clear()
    G[2] = 7


def grow(d: dict[str, int], n: int) -> None:
    # enough insertions to rebuild the table: every entry moves
    for i in range(n):
        d["g" + str(i)] = i


def drop(d: dict[str, int], k: str) -> None:
    del d[k]


def counting(words: list[str]) -> None:
    d: dict[str, int] = {}
    for w in words:
        if w in d:
            d[w] += 1
        else:
            d[w] = 1
    print(d)
    e: dict[str, int] = {}
    for w in words:
        if w not in e:
            e[w] = 0
        e[w] += 1
    print(e, e == d)
    f: dict[int, int] = {}
    for w in words:
        f[len(w)] = 0
    for w in words:
        f[len(w)] = f[len(w)] + 1
    print(f)


def reads() -> None:
    d = {"a": 1, "b": 2}
    for k in ["a", "c", "b"]:
        if k in d:
            v = d[k]
            print(k, v, end="; ")
        x = d[k] if k in d else -1
        print(x, end="; ")
    print()
    m: dict[int, list[int]] = {}
    for i in range(6):
        if i % 3 in m:
            m[i % 3].append(i)
        else:
            m[i % 3] = [i]
    print(m)
    s: dict[str, str] = {"k": "v"}
    if "k" in s:
        s["k"] = s["k"] + "w"
    print(s)


def changes() -> None:
    d = {"a": 1, "b": 2, "c": 3}
    if "a" in d:
        grow(d, 40)  # a rebuild moves the entries
        d["a"] += 1000
    print(d["a"], len(d), list(d)[:4])
    if "b" in d:
        drop(d, "b")
        d["b"] = 5  # inserted again, at the end
    print(list(d)[-2:], d["b"])
    if "c" in d:
        d.pop("c")
        d["c"] = 9
    print(list(d)[-1], d["c"])
    if "a" in d:
        d.clear()
        d["a"] = 0
    print(d)
    e = d
    if "a" in d:
        e["z"] = 1  # the same dict through another variable
        e.pop("a")
        d["a"] = 2
    print(d, e)
    if 1 in G:
        clear_global()  # a function that changes a global dict
        G[1] = G[2] + 1
    print(G)
    c = Counter()
    for w in ["p", "q", "p", "p"]:
        c.add(w)
    print(c.d, c.n)
    c.bump_after_reset("p")
    print(c.d)
    t = {"x": 1}
    u = {"x": 2}
    if "x" in t:
        t = u  # another dict in the same variable
        t["x"] += 10
    print(t, u)
    k1 = "a" + "b"
    k2 = "ab"
    h = {"ab": 1}
    if k1 in h:
        h[k2] += 1  # an equal key in another str
    print(h)


def many() -> None:
    # more lookups than hold at once (LOOKUPS): the oldest gives way
    d: dict[int, int] = {}
    for i in range(40):
        d[i] = i * i
    t = d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[4] ^ d[5] ^ d[6] ^ d[7] ^ d[8] ^ d[9] ^ d[10] ^ d[11] ^ d[12] ^ d[13] ^ d[14] ^ d[15]
    t ^= d[16] ^ d[17] ^ d[18] ^ d[19] ^ d[20] ^ d[21] ^ d[22] ^ d[23] ^ d[24] ^ d[25] ^ d[26] ^ d[27] ^ d[28] ^ d[29] ^ d[30] ^ d[31]
    d[33] = d[32] + d[33] + t
    d[0] = d[1] + t
    print(t, d[0], d[33], len(d))


counting(["x", "y", "x", "zz", "x", "y"])
reads()
changes()
many()
counts = {"seen": 1}
counts["seen"] = counts["seen"] + 1
print(counts)
counts["missing"] = counts["missing"] + 1
print("never")
