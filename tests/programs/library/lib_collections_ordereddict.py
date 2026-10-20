# lib/collections: OrderedDict, a generic class over a dict, against CPython's C type
# (Objects/odictobject.c): construction, move_to_end, popitem, order-sensitive equality, the
# dict methods, | and an LRU cache as cachetools builds one.
from collections import OrderedDict, defaultdict

# constructors
print(OrderedDict[str, int](), OrderedDict({"b": 2, "a": 1}), OrderedDict([("x", 1.5), ("y", 2.5)]))
print(OrderedDict((("t", [1]), ("u", [2]))), OrderedDict({("k", 1)}))
src = OrderedDict([("p", 1), ("q", 2)])
cp = OrderedDict(src)
cp["r"] = 3
print(src, cp, src.copy(), OrderedDict(sorted({"z": 1, "a": 2}.items())))
dd: defaultdict[str, int] = defaultdict(int, {"d": 4})
print(OrderedDict(dd))
e: OrderedDict[str, int] = OrderedDict()
print(e, len(e), bool(e), OrderedDict[int, str]())
print(OrderedDict.fromkeys("abc", 0), OrderedDict.fromkeys(["x", "y", "x"], [1]), OrderedDict.fromkeys("", 1.5))

# a value's position is its key's first insertion; reversed() steps back through them
f = OrderedDict([("one", 1), ("two", 2), ("three", 3)])
print(list(reversed(f)), list(reversed(f.items())), [k for k in reversed(f) if k != "two"])

# order operations
od = OrderedDict([(ch, i) for i, ch in enumerate("abcde")])
od.move_to_end("b")
print(list(od), od)
od.move_to_end("b", last=False)
od.move_to_end("e", False)
print(list(od.keys()), list(od.values()), list(od.items()))
od.move_to_end("a")
od.move_to_end("a")
print(od)
try:
    od.move_to_end("zz")
except KeyError as ex:
    print("KeyError", ex, repr(ex))
try:
    OrderedDict[str, int]().move_to_end("x")
except KeyError as ex:
    print("KeyError", ex)
print(od.popitem(), od.popitem(last=False), od.popitem(False), od)
od["c"] = 100
od["n"] = 5
print(od)
del od["c"]
print(od, "c" in od, "n" in od)
try:
    del od["c"]
except KeyError as ex:
    print("KeyError", ex)
try:
    print(od["c"])
except KeyError as ex:
    print("KeyError", ex)
small = OrderedDict([("only", 1)])
print(small.popitem(), small)
try:
    small.popitem()
except KeyError as ex:
    print("KeyError", ex, repr(ex))
try:
    small.popitem(last=False)
except KeyError as ex:
    print("KeyError", ex)

# reinsertion keeps position; deletion and reinsertion moves to the end
o2 = OrderedDict([("a", 1), ("b", 2), ("c", 3)])
o2["a"] = 10
print(o2)
del o2["a"]
o2["a"] = 11
print(o2)

# equality: order-sensitive between OrderedDicts
x = OrderedDict([("a", 1), ("b", 2)])
y = OrderedDict([("b", 2), ("a", 1)])
print(x == y, x != y, x == OrderedDict(x), x != x.copy())
y.move_to_end("b")
print(x == y, x != y)
print(OrderedDict([("a", 1)]) == OrderedDict([("a", 2)]))
# order-insensitive with a dict and other mappings, also in containers
od = OrderedDict({"a": 1, "b": 2})
od2 = OrderedDict({"b": 2, "a": 1})
print(od == {"b": 2, "a": 1}, od != {"a": 1}, od == od2, od != od2, od == od.copy())
dd2: defaultdict[str, int] = defaultdict(int, {"a": 1})
print(dd2 == {"a": 1}, dd2 != {"a": 2}, dd2 == dd2.copy(), dd2 == OrderedDict({"a": 1}), od == dd2)
print([od] == [od2], [od] == [od.copy()], od in [od2, od], dd2 in [dd2])

# dict API
print(x.get("a"), x.get("z"), x.get("z", -1), x.setdefault("a", 5), x.setdefault("c", 3), x)
print(x.pop("c"), x.pop("zz", 0), x.pop("zz", None), x)
try:
    x.pop("zz")
except KeyError as ex:
    print("KeyError", ex)
x.update({"m": 7}, n=8)
x.update([("o", 9)])
x.update(OrderedDict([("a", -1)]))
print(x)
print(x | {"q": 1}, x | OrderedDict([("a", 0)]))
x |= {"r": 2}
print(x)
for key in x:
    print(key, x[key])
print([k * 2 for k in x], sorted(x), max(x))
x.clear()
print(x, len(x))

# the operations at both ends, interleaved: every view of the order agrees
w = OrderedDict([(ch, i) for i, ch in enumerate("abcdefgh")])
print(w.popitem(last=False), w.popitem(), w.popitem(False), list(w))
w.move_to_end("f", last=False)
w.move_to_end("c")
w["b"] = -1
w["z"] = 26
w["f"] = 60
print(w, len(w), list(w), list(reversed(w)), list(w.keys()), list(w.values()), list(w.items()))
print("f" in w, "b" in w, "a" in w, w["f"], w.get("f"), w.get("a", 0), w.setdefault("f", 0), w.setdefault("y", 25))
print(w.pop("f"), w.pop("d"), w.pop("a", None), w, w == w.copy(), w.copy())
del w["e"]
w.move_to_end("z", False)
w.move_to_end("y", False)
print(w, w == OrderedDict([("y", 25), ("z", 26), ("g", 6), ("c", 2), ("b", -1)]), w != OrderedDict(w.items()))
print(w == {"c": 2, "b": -1, "z": 26, "y": 25, "g": 6}, w | {"q": 0}, OrderedDict(w))
counted: defaultdict[str, int] = defaultdict(int, w)
print(counted, counted == w, w == counted)
while w:
    print(w.popitem(last=len(w) % 2 == 0), end=" ")
print(w, len(w))
w["new"] = 1
w.move_to_end("new", last=False)
print(w, w.popitem(last=False), w)
fifo = OrderedDict([(i, str(i)) for i in range(1000)])
firsts = [fifo.popitem(last=False)[0] for _ in range(500)]
lasts = [fifo.popitem()[0] for _ in range(250)]
print(firsts[:3], firsts[-1], lasts[:3], lasts[-1], len(fifo), list(fifo)[:2], list(fifo)[-2:])
for i in range(1000, 1010):
    fifo[i] = str(i)
    fifo.move_to_end(i - 1000 + 500, last=False)
print(list(fifo)[:12], list(reversed(fifo))[:3], len(fifo))
order: list[int] = []
while fifo:
    order.append(fifo.popitem(last=len(order) % 3 != 0)[0])
print(order[:8], len(order), sorted(order) == sorted(set(order)))

# LRU cache over an OrderedDict (as cachetools.LRUCache does)


class LRU:
    def __init__(self, size: int) -> None:
        self.size = size
        self.data: OrderedDict[str, int] = OrderedDict()
        self.hits = 0

    def get(self, key: str) -> int | None:
        if key in self.data:
            self.data.move_to_end(key)
            self.hits += 1
            return self.data[key]
        return None

    def put(self, key: str, value: int) -> None:
        self.data[key] = value
        self.data.move_to_end(key)
        if len(self.data) > self.size:
            print("evict", self.data.popitem(last=False))


cache = LRU(2)
cache.put("a", 1)
cache.put("b", 2)
print(cache.get("a"), cache.get("c"))
cache.put("c", 3)
cache.put("d", 4)
print(cache.data, cache.hits)


def rank(scores: dict[str, int]) -> OrderedDict[str, int]:
    return OrderedDict(sorted(scores.items(), key=lambda kv: kv[1], reverse=True))


print(rank({"ann": 3, "bob": 9, "eve": 5, "zoë": 9}))

# used as a stack, a push and a popitem() in turn, and as a queue
stack: OrderedDict[str, int] = OrderedDict()
stack["bottom"] = 0
for j in range(2000):
    stack["k" + str(j)] = j
    if j % 3 != 2:
        stack.popitem()
print(len(stack), list(stack.items())[:3], stack.popitem(), stack.popitem(last=False))
queue: OrderedDict[int, int] = OrderedDict()
for j in range(2000):
    queue[j] = j * j
    if j % 2 == 1:
        queue.popitem(last=False)
print(len(queue), queue.popitem(last=False), queue.popitem(), 1999 in queue, 1001 in queue)
