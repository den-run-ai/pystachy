# lib/collections: Counter, a generic class over a dict of int counts, against CPython's
# (Lib/collections/__init__.py): construction, counting, the dict methods, multiset arithmetic
# and the 3.10 comparisons, where missing counts are zero.
from collections import Counter, OrderedDict, defaultdict

# constructors: an iterable, a mapping, another Counter, an annotation or explicit type
print(Counter("hello world"), Counter("élan à la çà".split()), Counter(["a", "b", "a"]), Counter(("x", "y", "x")))
print(Counter({"a": 2, "b": -1}), Counter([1, 2, 2, 3, 3, 3]), Counter({(1, "x"): 2}), Counter([(1, True), (1, True)]))
c1 = Counter("aab")
c2 = Counter(c1)
c2["a"] += 10
print(c1, c2, c1.copy(), c1.copy() == c1, Counter(OrderedDict({"q": 4})))
dd: defaultdict[str, int] = defaultdict(int)
dd["z"] += 3
print(Counter(dd))
n: Counter[int] = Counter()
print(n, bool(n), len(n), Counter[str](), Counter[str]("ab"))

# missing elements count zero, without being added; del does not raise
c = Counter("mississippi")
print(c["s"], c["z"], "z" in c, len(c), c.__missing__("q"), c)
del c["m"]
del c["absent"]
print(c, "m" in c, c["m"])

# update and subtract: iterables, mappings, Counters and keyword arguments
c = Counter("which")
c.update("witch")
c.update(Counter("watch"))
c.update({"h": 1, "q": 0})
c.update(a=1, b=2)
print(c, c["h"])
c.subtract("witch")
c.subtract(Counter("watch"))
c.subtract({"q": 5})
c.subtract(a=1)
print(c, c["w"])
e: Counter[str] = Counter()
e.update({"m": 2, "n": 0})
e.update()
e.subtract()
e.update(e)
print(e)

# the dict methods
c = Counter("mississippi")
print(list(c.keys()), list(c.values()), list(c.items()))
print(c.get("s"), c.get("z"), c.get("z", 7), c.setdefault("s", 99), c.setdefault("y", 1), c)
print(c.pop("y"), c.pop("nope", -1), c.pop("nope", None), c.popitem(), c)
try:
    c.pop("nope")
except KeyError as ex:
    print("KeyError", ex)
for k in c:
    print(k, c[k])
print(sorted(c), list(c), [k * 2 for k in c], max(c), min(c), list(reversed(c)))
c.clear()
print(c, c.total(), c.most_common(), list(c.elements()))
try:
    c.popitem()
except KeyError as ex:
    print("KeyError", ex)
try:
    Counter.fromkeys("abc")
except NotImplementedError as ex:
    print("NotImplementedError", ex)

# most_common: ties keep their first-seen order; n <= 0 gives nothing
c = Counter("abracadabra")
print(c.most_common(2), c.most_common(), c.most_common(0), c.most_common(-1), c.most_common(10))
print(Counter({"a": 1, "b": 1, "c": 2}).most_common(), Counter({"x": 0, "y": -1}).most_common(1))
print(sorted(c.elements()), list(Counter({"x": 2, "y": 0, "z": -1, "w": 1}).elements()), c.total())
print(sum(Counter({2: 2, 3: 3}).elements()), Counter({"neg": -3}).total())

# multiset arithmetic keeps positive counts
a = Counter("abbb")
b = Counter("bcc")
print(a + b, a - b, a | b, a & b, b - a)
x = Counter({"a": 3, "b": -2, "c": 0})
print(+x, -x, x + Counter(), x - Counter(), Counter[str]() - x, x | Counter(), x & x)
a += b
print(a)
a -= Counter("bbbbbbbb")
print(a)
a |= Counter("aaaz")
print(a)
a &= Counter("az")
print(a)
y = Counter({"p": 1, "q": -1})
y += Counter()
print(y)

# comparisons (3.10): missing counts are zero
p = Counter({"a": 1, "b": 0})
q = Counter({"a": 1})
print(p == q, p != q, p <= q, p < q, p >= q, p > q)
r = Counter({"a": 2, "c": 1})
print(q < r, r > q, q <= r, r <= q, q == r, q != r, Counter({"z": 0}) == Counter())
# with a dict, equality is dict's: the items must match
print(p == {"a": 1, "b": 0}, p == {"a": 1}, p != {"a": 1}, [p] == [q], q in [p])
# and with the other mappings (CPython reflects to theirs, a dict's)
print(q == OrderedDict({"a": 1}), p == OrderedDict({"a": 1}), OrderedDict({"a": 1}) == p, p != dd, dd != p)

# word counts at module level, in functions, methods, fields and closures
text = "the cat and the hat and the bat"
counts: Counter[str] = Counter()
for word in text.split():
    counts[word] += 1
for word, num in counts.most_common(3):
    print(f"{word}: {num}")
print(counts.total(), len(counts))


class Stats:
    def __init__(self) -> None:
        self.seen: Counter[str] = Counter()

    def add(self, s: str) -> None:
        self.seen.update(s.split())

    def top(self) -> str:
        return self.seen.most_common(1)[0][0]


def top(words: list[str], k: int) -> list[tuple[str, int]]:
    return Counter(words).most_common(k)


def tally(lines: list[str]) -> Counter[str]:
    total: Counter[str] = Counter()
    for line in lines:
        total.update(line.split())
    return total


def local(x: str) -> None:
    # (the import of a function's own)
    from collections import Counter
    print(Counter(x))


def counter_of(words: list[str]):
    seen: Counter[str] = Counter()

    def add(w: str) -> int:
        seen[w] += 1
        return seen[w]

    return [add(w) for w in words]


st = Stats()
st.add("a b a")
st.add("b c b")
print(st.seen, st.top(), top(["x", "y", "x"], 1), tally(["a b", "b ω", "ω ω"]))
local("aab")
print(counter_of(["p", "q", "p", "p"]))
# counts and popitem() in turn
churn = Counter("ab")
for j in range(2000):
    churn["k" + str(j % 70)] += 1
    if j % 4 != 0:
        churn.popitem()
print(len(churn), churn.most_common(3), churn.total())
