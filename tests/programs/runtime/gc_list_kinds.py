# The item arrays of lists of ints, floats and bools are memory the collector does not scan (#210);
# every other list's array is scanned. Run with PYSTACHY_GC_STRESS_PROGRAM=1 (the gc-stress step),
# which collects at every allocation: a str, list or object that only an unscanned array referred to
# would be freed and its memory zeroed, and a checksum of the strs would change. The lists whose
# types are decided after they are made: an empty list a template returns, which each call's context
# types (list[int] in one, list[str] in another), and one whose first use decides it (xs = [], then
# xs.append); then displays, comprehensions, list(), copies, slices, + and *, growth, clear() and
# sorts of each kind, nested lists, fields, globals and closures.


def digest(xs: list[str]) -> int:
    # an order-sensitive checksum of every character of every str
    h = len(xs)
    for x in xs:
        for c in x:
            h = (h * 31 + ord(c)) % 1000000007
        h = (h * 37 + 11) % 1000000007
    return h


def make_list(n):
    xs = []
    return xs


def fresh(n):
    return []


def forward(n):
    return make_list(n)


def first_or_empty(flag):
    # a later return decides the empty result's type: list[float]
    if flag:
        return []
    return [1.5]


def built(flag):
    # an empty local returned before the append that decides its type: list[str]
    xs = []
    if flag:
        return xs
    xs.append("built")
    return xs


nums: list[int] = make_list(1)
names: list[str] = make_list(2)
floats: list[float] = fresh(3)
words: list[str] = fresh(4)
flags: list[bool] = forward(5)
labels: list[str] = forward(6)
halves = first_or_empty(True)
tags = built(True)
for i in range(300):
    nums.append(i * 1000003)
    names.append(str(i) * 40)
    floats.append(i / 7.0)
    words.append("w" + str(i))
    flags.append(i % 3 == 0)
    labels.append(str(i * i))
    halves.append(i * 0.5)
    tags.append("t" + str(i % 10))
print(len(nums), sum(nums), sum(floats), flags.count(True), sum(halves), first_or_empty(False), built(False))
print(digest(names), digest(words), digest(labels), digest(tags), names[299][:9], words[-1], labels[17])


class Bag:
    def __init__(self) -> None:
        self.counts: list[int] = []
        self.names: list[str] = []
        self.pending: list[str] = []

    def add(self, k: int) -> None:
        self.counts.append(k)
        self.names.append("n" + str(k))
        self.pending.append(str(k) * 3)


class Box[T]:
    def __init__(self, first: T) -> None:
        self.items: list[T] = []
        self.items.append(first)

    def put(self, x: T) -> None:
        self.items.append(x)


def local_kinds(n: int) -> list[str]:
    xs = []
    ys = []
    zs = []
    for i in range(n):
        xs.append(i)
        ys.append("y" + str(i))
        zs.append(float(i))
    ws = ys[::-1] + ys[:2]
    ws.extend(ys)
    ws.insert(1, "first")
    ws[3:6] = ["a", "b", "c", "d"]
    del ws[0]
    return ws + [str(len(xs) + sum(xs)), str(sum(zs))]


bag = Bag()
ints = Box(1)
strs = Box("s")
pairs = Box((1, "one"))
for i in range(200):
    bag.add(i)
    ints.put(i * 3)
    strs.put("item" + str(i))
    pairs.put((i, "p" + str(i)))
lk = local_kinds(150)
print(sum(bag.counts), sum(ints.items), digest(bag.names), digest(bag.pending), digest(strs.items), digest([p[1] for p in pairs.items]))
print(len(lk), lk[:4], lk[-3:], digest(lk))

# displays, comprehensions, list() and the copies of each kind
grid = [[0.0] * 3 for _ in range(4)]
for r in range(4):
    for c in range(3):
        grid[r][c] = r * 10.0 + c
rows = [[str(r)] * 2 for r in range(50)]
ids = [i * i for i in range(100)]
bits = [i % 2 == 0 for i in range(100)]
strs2 = [str(i) for i in range(100)]
opt: list[int | None] = [1, None, 3]
mixed: list[int | str] = [1, "two", 3]
objs = [Bag() for _ in range(3)]
for o in objs:
    o.add(5)
star = [*ids[:3], 7, *ids[-2:]]
sstar = [*strs2[:2], "x" * 50, *strs2[-1:]]
tup = list((1.5, 2.5, 3.5))
copies = [ids.copy(), ids[10:20], ids[::7], ids + ids, ids * 2, list(ids), sorted(ids, key=lambda x: -x)]
scopies = [strs2.copy(), strs2[10:20], strs2[::7], strs2 + strs2, strs2 * 2, list(strs2), sorted(strs2, key=len)]
print(grid, sum(ids), bits.count(True), opt, mixed, objs[2].names, star, tup)
print(digest([r[0] + r[1] for r in rows]), digest(strs2), digest(sstar), [len(c) for c in copies], [c[-1] for c in copies], [digest(c) for c in scopies])

# clearing keeps a list's kind: refilled after clear() and after emptying deletes
for xs in [ids, copies[0]]:
    xs.clear()
    for i in range(40):
        xs.append(i)
for ss in [strs2, scopies[0]]:
    del ss[:]
    for i in range(40):
        ss.append(str(i) * 9)
words.sort(key=len)
nums.sort(reverse=True)
print(ids[-1], copies[0][-1], digest(strs2), digest(scopies[0]), digest(words), nums[:2])

# dict keys and values, set elements and items as lists
d: dict[int, str] = {}
for i in range(100):
    d[i * 7] = "v" + str(i)
keys = list(d)
vals = list(d.values())
items = list(d.items())
s = {i * 11 for i in range(100)}
elems = sorted(s)
for i in range(100):
    keys.append(i)
    vals.append("w" + str(i))
    elems.append(i)
print(len(keys), keys[99], digest(vals), digest([kv[1] for kv in items]), len(elems), elems[99], max(elems))


def counter():
    seen: list[str] = []

    def note(x: str) -> int:
        seen.append(x * 2)
        return len(seen)

    return note, seen


note, seen = counter()
for i in range(100):
    note(str(i))
print(len(seen), digest(seen))
