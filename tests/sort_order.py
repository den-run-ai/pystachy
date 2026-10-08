# list.sort and sorted() make exactly CPython's (timsort's) sequence of < comparisons, which is
# observable: where NaNs end up, how often and in which order __lt__ runs, what inconsistent
# comparisons produce, and that the list looks empty to __lt__ while it is being sorted.
M = 2147483629
calls: list[str] = []
log = False
evil = False
ncalls = 0
h = 1
seed = 1


class C:
    def __init__(self, v: int, i: int):
        self.v = v
        self.i = i

    def __lt__(self, o: "C") -> bool:
        global ncalls, h
        ncalls += 1
        h = (h * 1000003 + self.i * 4099 + o.i + 1) % M
        if log:
            calls.append(f"{self.v}<{o.v}")
        if evil:
            return h % 3 == 0
        return self.v < o.v


def rnd(n: int) -> int:
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return (seed >> 8) % n


def objs(vs: list[int]) -> list[C]:
    return [C(vs[i], i) for i in range(len(vs))]


def show(vs: list[int]) -> None:
    # the comparisons sorting vs makes, in order
    global log, calls
    log = True
    calls = []
    cs = objs(vs)
    cs.sort()
    log = False
    print(vs, "->", [c.v for c in cs], len(calls), " ".join(calls))


def phash(cs: list[C]) -> int:
    g = 5
    for c in cs:
        g = (g * 1009 + c.i + 1) % M
    return g


def shash(s: str) -> int:
    g = 7
    for ch in s:
        g = (g * 131 + ord(ch)) % M
    return g


def make(n: int, shape: int, k: int) -> list[int]:
    xs: list[int] = []
    for i in range(n):
        if shape == 0:
            xs.append(rnd(k))                        # random, k distinct values
        elif shape == 1:
            xs.append(i // k)                        # ascending with equal stretches
        elif shape == 2:
            xs.append((n - i) // k)                  # descending with equal stretches
        elif shape == 3:
            xs.append(i % k)                         # sawtooth
        elif shape == 4:
            xs.append(i if rnd(16) > 0 else rnd(n))  # nearly sorted
        elif shape == 5:
            xs.append((i // k) * 3 - i % k)          # short descending runs, rising
        elif shape == 6:                             # two sorted sequences in long blocks: galloping
            xs.append(i // 2 + (0 if (i // k) % 2 == 0 else n // 3))
        else:
            xs.append(rnd(k) if rnd(4) > 0 else -1)  # random with many equal items
    return xs


print(sorted([3.0, float("nan"), 1.0, 2.0, 0.5]))
nan = float("nan")
print(sorted([nan, 2.0, 1.0]), sorted([2.0, nan, 1.0, 0.0]), sorted([1.0, nan, 0.5, nan, -1.0, 7.0, 2.5]))
print(sorted([0.0, -0.0, 0.0, -0.0]), sorted([5.0, 4.0, nan, 3.0, 2.0, 1.0, nan, 0.0]))
show([1, 2, 3, 4])
show([4, 3, 2, 1, 5])
show([2, 1])
show([1, 1, 1])
show([3, 3, 2, 2, 1, 1, 5, 4])
show([5, 1, 4, 2, 3, 9, 0, 7, 8, 6])
show([1, 2, 3, 2, 1, 0, 0, -1, 5, 6])

# stability: equal keys keep their order
cs = objs([2, 1, 2, 1, 0, 2, 1, 0])
print([f"{c.v}.{c.i}" for c in sorted(cs)])

# deterministic pseudo-random lists of many shapes and sizes: count, call order (as a hash) and
# result of the comparisons on objects; results for plain ints, floats with NaNs, strs, tuples
sizes = [0, 1, 2, 3, 5, 8, 13, 21, 31, 32, 33, 47, 63, 64, 65, 70, 100, 127, 128, 129, 200, 257, 400, 700, 1025, 2000]
for case in range(260):
    n = sizes[case % len(sizes)] if case < 208 else rnd(2000)
    shape = case % 8
    k = 1 + rnd(n + 2) if case % 3 else 1 + rnd(5)
    evil = case % 13 == 12
    vs = make(n, shape, k)
    cs = objs(vs)
    ncalls = 0
    h = 1
    if case % 2:
        cs.sort()
    else:
        cs = sorted(cs)
    evil = False
    xs = [v for v in vs]
    xs.sort()
    fs = [nan if v % 7 == 3 else v / 4 for v in vs]
    fs.sort()
    ss = sorted([str(v) for v in vs])
    ts = sorted([(v % 3, str(v)) for v in vs])
    print(case, n, shape, k, ncalls, h, phash(cs), shash(str(xs)), shash(str(fs)), shash(str(ss)), shash(str(ts)))


# while it is sorted, the list looks empty to __lt__, and changes that leave it empty are fine
class D:
    def __init__(self, v: int):
        self.v = v

    def __lt__(self, o: "D") -> bool:
        global target
        seen.append(len(target))
        target.clear()
        target.extend([])
        target.reverse()
        target.sort()
        target *= 3
        if len(seen) == 1:
            print("inside:", target, sorted(target), D(0) in target)
        return self.v < o.v


seen: list[int] = []
target = [D(3), D(1), D(2), D(5), D(4)]
target.sort()
print([d.v for d in target], len(target), len(seen), sum(seen))
