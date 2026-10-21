# lib/collections: the other operand of a mapping's (and deque's) comparisons and operators,
# where CPython's methods return NotImplemented: == and != of None or a non-mapping (an
# identity test), CPython's TypeError for < & co, + & co and | of a non-dict, and the mappings
# with each other, in optional variables, function results, fields and methods.
from collections import Counter, OrderedDict, defaultdict, deque


def cfind(flag: bool) -> Counter[str] | None:
    return Counter("ab") if flag else None


def ofind(flag: bool) -> OrderedDict[str, int] | None:
    return OrderedDict([("a", 1), ("b", 1)]) if flag else None


def dfind(flag: bool) -> defaultdict[str, int] | None:
    d: defaultdict[str, int] = defaultdict(int, {"a": 1, "b": 1})
    return d if flag else None


def qfind(flag: bool) -> deque[int] | None:
    return deque([1, 2]) if flag else None


def mfind(flag: bool) -> dict[str, int] | None:
    return {"a": 1, "b": 1} if flag else None


c = Counter("ab")
od = OrderedDict([("a", 1), ("b", 1)])
dd: defaultdict[str, int] = defaultdict(int, {"a": 1, "b": 1})
q = deque([1, 2])
for flag in [True, False]:
    print(c == cfind(flag), c != cfind(flag), cfind(flag) == c, c == ofind(flag), c == dfind(flag), c == mfind(flag), c != mfind(flag))
    print(od == ofind(flag), od != ofind(flag), od == cfind(flag), od == dfind(flag), od == mfind(flag), od != dfind(flag))
    print(dd == dfind(flag), dd != dfind(flag), dd == cfind(flag), dd == ofind(flag), dd == mfind(flag), dd != mfind(flag))
    print(q == qfind(flag), q != qfind(flag), qfind(flag) == q)
print(c == None, c != None, od == None, od != None, dd == None, dd != None, q == None, q != None)
print(od == 5, c == [1], dd == "ab", od != 5, c != (1, 2), dd != 2.5, c == "ab", od == ("a", 1))
print(c == {"a": 1, "b": 1}, od == {"b": 1, "a": 1}, dd == {"a": 1, "b": 1}, c == od, od == c, dd == c, od == dd)
print(OrderedDict([("b", 1), ("a", 1)]) == od, OrderedDict([("b", 1), ("a", 1)]) == dd, Counter("ba") == c)

n = cfind(False)
for name in ["le", "lt", "ge", "gt", "add", "sub", "or", "and"]:
    try:
        if name == "le":
            print(c <= n)
        elif name == "lt":
            print(c < n)
        elif name == "ge":
            print(c >= n)
        elif name == "gt":
            print(c > n)
        elif name == "add":
            print(c + n)
        elif name == "sub":
            print(c - n)
        elif name == "or":
            print(c | n)
        else:
            print(c & n)
    except TypeError as e:
        print("TypeError", e)
qn = qfind(False)
for name in ["lt", "le", "gt", "ge"]:
    try:
        if name == "lt":
            print(q < qn)
        elif name == "le":
            print(q <= qn)
        elif name == "gt":
            print(q > qn)
        else:
            print(q >= qn)
    except TypeError as e:
        print("TypeError", e)
print(q < qfind(True), q <= qfind(True), q > deque([1]), q >= deque([3]))

# | takes a dict or another mapping (|= also an iterable of pairs, as update)
for k in range(7):
    try:
        if k == 0:
            print(dd | (("a", 2),))
        elif k == 1:
            print(od | [("b", 2)])
        elif k == 2:
            print(dd | {("x", 1)})
        elif k == 3:
            print(od | dfind(False))
        elif k == 4:
            print(dd | mfind(False))
        elif k == 5:
            print(od | 5)
        else:
            print(dd | "ab")
    except TypeError as e:
        print("TypeError", e)
print(dd | mfind(True), od | ofind(True), od | c, dd | c)
print(od | dd, dd | od, dd | {"z": 3}, od | {"z": 3, "a": 0})
try:
    merged = od | [("b", 2)]
    print("merged", merged)
except TypeError as e:
    print("TypeError", e)
dd |= [("y", 4)]
od |= (("y", 4),)
print(dd, od)

# a Counter as the items of an OrderedDict or defaultdict
w: OrderedDict[str, int] = OrderedDict(Counter("abca"))
x: defaultdict[str, int] = defaultdict(int, Counter(["ω", "é", "ω"]))
x["new"] += 1
print(w, x, OrderedDict[str, int](Counter("zz")))


class Tally:
    def __init__(self) -> None:
        self.last: Counter[str] | None = None
        self.now: Counter[str] = Counter()

    def step(self, text: str) -> bool:
        self.last = self.now
        self.now = Counter(text)
        return self.now == self.last


t = Tally()
print(t.now == t.last, t.now != t.last, t.step("aba"), t.step("baa"), t.step("ab"))
