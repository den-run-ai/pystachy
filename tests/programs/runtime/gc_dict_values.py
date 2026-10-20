# The value arrays of dicts whose values are ints, floats or bools are memory the collector does
# not scan (#210); other dicts' value arrays are scanned. Run with PYSTACHY_GC_STRESS_PROGRAM=1 (the
# gc-stress step), which collects at every allocation: a str, list or object that only an unscanned
# array referred to would be freed and its memory zeroed, and a checksum of the strs would change.
# The dicts whose types are decided after they are made: an empty dict a template returns, which
# each call's context types (dict[str, int] in one, dict[str, str] in another), and one whose first
# use decides it (d = {}, then d[k] = v); then displays, comprehensions, dict(), copies, |, update,
# setdefault, clear() and the values() lists of each kind.


def digest(xs: list[str]) -> int:
    # an order-sensitive checksum of every character of every str
    h = len(xs)
    for x in xs:
        for c in x:
            h = (h * 31 + ord(c)) % 1000000007
        h = (h * 37 + 11) % 1000000007
    return h


def make_dict(n):
    d = {}
    return d


def fresh(n):
    return {}


def forward(n):
    return make_dict(n)


counts: dict[str, int] = make_dict(1)
names: dict[str, str] = make_dict(2)
scores: dict[int, float] = fresh(3)
labels: dict[int, str] = fresh(4)
seen: dict[str, bool] = forward(5)
groups: dict[str, list[str]] = forward(6)
for i in range(300):
    k = "k" + str(i % 97)
    counts[k] = counts.get(k, 0) + i
    names[k] = str(i) * 9
    scores[i] = i / 8.0
    labels[i * 7] = "label" + str(i)
    seen[str(i % 50)] = i % 2 == 0
    groups.setdefault(k, []).append("g" + str(i))
print(len(counts), sum(counts.values()), sum(scores.values()), list(seen.values()).count(True))
print(digest(list(names.values())), digest(list(labels.values())), digest([x for v in groups.values() for x in v]))


def local_kinds(n: int) -> list[str]:
    a = {}
    b = {}
    for i in range(n):
        a["x" + str(i)] = i * 3
        b[i] = "y" + str(i)
    c = dict(a)
    c.update({"extra": 1})
    e = b.copy()
    e[-1] = "minus"
    f = {**b, 10000: "big"}
    return [str(sum(c.values())), str(len(e))] + list(e.values())[-3:] + list(f.values())[:3]


lk = local_kinds(200)
print(lk, digest(lk))

# displays, comprehensions, dict(), copies, | and the values lists of each kind
sq = {i: i * i for i in range(200)}
fl = {str(i): i / 3.0 for i in range(200)}
bl = {i: i % 3 == 0 for i in range(200)}
st = {i: "s" + str(i) for i in range(200)}
disp = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6, "g": 7}
sdisp = {"a": "x" * 30, "b": "y" * 30, "c": "z" * 30, "d": "w" * 30, "e": "v" * 30, "f": "u" * 30}
pairs = dict([(str(i), i) for i in range(100)])
spairs = dict([(i, str(i) * 4) for i in range(100)])
merged = sq | {1000: 1}
smerged = st | {1000: "thousand"}
cps = [sq.copy(), dict(sq), {**sq}]
scps = [st.copy(), dict(st), {**st}]
for i in range(200, 260):
    sq[i] = -i
    st[i] = "t" + str(i)
    for c in cps:
        c[i] = i
    for sc in scps:
        sc[i] = "c" + str(i)
print(sum(sq.values()), sum(fl.values()), list(bl.values()).count(True), sum(disp.values()), sum(pairs.values()), sum(merged.values()))
print(digest(list(st.values())), digest(list(sdisp.values())), digest(list(spairs.values())), digest(list(smerged.values())))
print([sum(c.values()) for c in cps], [digest(list(sc.values())) for sc in scps])

# clearing keeps a dict's kind: refilled after clear()
for d in [sq, cps[0]]:
    d.clear()
    for i in range(50):
        d[i] = i * 2
for sd in [st, scps[0]]:
    sd.clear()
    for i in range(50):
        sd[i] = str(i) * 7
print(sum(sq.values()), sum(cps[0].values()), digest(list(st.values())), digest(list(scps[0].values())))
vals = list(sq.values())
svals = list(st.values())
for i in range(100):
    vals.append(i)
    svals.append("v" + str(i))
print(sum(vals), digest(svals), sq.pop(3), st.pop(3), sq.popitem(), st.popitem())


class Table:
    def __init__(self) -> None:
        self.weights: dict[str, float] = {}
        self.notes: dict[str, str] = {}

    def add(self, k: int) -> None:
        self.weights["w" + str(k)] = k * 0.25
        self.notes["n" + str(k)] = "note" + str(k) * 3


t = Table()
for i in range(150):
    t.add(i)
print(sum(t.weights.values()), digest(list(t.notes.values())))
