# dict.popitem(): the last item, removed and returned as a (key, value) tuple (LIFO); an empty
# dict raises KeyError('popitem(): dictionary is empty'). As CPython's, it truncates the entries
# (the next insertion takes the popped one's place) but does not give the table those entries
# back, so the next insertion rebuilds the table where CPython's does, which decides what a loop
# that changes the dict sees.
from typing import Callable


def show(d: dict[str, int]) -> None:
    while d:
        k, v = d.popitem()
        print(k, v, len(d), end="; ")
    print(d)


d = {"a": 1, "b": 2, "c": 3}
print(d.popitem(), d)
d["z"] = 26
print(d.popitem(), d.popitem(), d)
d["b"] = 20
d["a"] = 10
print(d)
show(d)
e: dict[str, int] = {}
try:
    e.popitem()
except KeyError as ex:
    print("KeyError", ex, repr(ex))
try:
    print(d.popitem())
except KeyError as ex:
    print("KeyError", str(ex))

# holes: the last item that is still there, and pops until the dict is empty
h = {"p": 1, "q": 2, "r": 3, "s": 4}
del h["s"]
del h["q"]
print(h.popitem(), h)
h["t"] = 5
print(h, h.popitem(), h.popitem(), h)
h["u"] = 6
print(h, list(h.items()))

# tuple keys, optional values, non-ASCII strs
t: dict[tuple[int, str], float | None] = {(1, "x"): None, (2, "é"): 2.5}
print(t.popitem(), t.popitem(), t)
u = {"naïve": "café", "日本": "語"}
k, v = u.popitem()
print(k, v, u)

# as a value, in a function, a method and a closure
pop = u.popitem
print(pop(), u)


class Stack:
    def __init__(self) -> None:
        self.items: dict[int, str] = {}

    def push(self, k: int, s: str) -> None:
        self.items[k] = s

    def pop(self) -> tuple[int, str]:
        return self.items.popitem()


st = Stack()
for i in range(5):
    st.push(i * i, str(i))
print(st.pop(), st.pop(), st.items)


def drainer(m: dict[int, str]) -> Callable[[], int]:
    def drain() -> int:
        n = 0
        while m:
            m.popitem()
            n += 1
        return n
    return drain


m = {1: "a", 2: "b", 3: "c"}
print(drainer(m)(), m)

# the table: popped entries are not free again until it is rebuilt
w: dict[int, int] = {}
for i in range(4):
    w[i] = i
seen: list[int] = []
for k2 in w:
    seen.append(k2)
    if k2 == 0:
        del w[0]
        w[100] = 0
    elif k2 == 1:
        print(w.popitem())
        w[200] = 0
print(seen, w)

x: dict[int, int] = {}
for i in range(5):
    x[i] = i
seen = []
try:
    for k2 in x:
        seen.append(k2)
        if k2 == 2:
            print(x.popitem())
            x[50] = 0
except RuntimeError as ex:
    print("RuntimeError", ex)
print(seen, x)

# copies take the table as it is (dict.copy() and dict(d) clone it), with what popitem spent
f: dict[int, int] = {}
for i in range(6):
    f[i] = i
del f[1]
print(f.popitem(), f.popitem())
g = f.copy()
c = dict(f)
f[7] = 7
g[7] = 7
c[7] = 7
print(f, g, c)
seen = []
for k2 in g:
    seen.append(k2)
    if k2 == 0:
        del g[2]
        g[8] = 8
print(seen, g)
y: dict[int, int] = {}
y.update(c)
print(y.popitem(), y)
y[9] = 9
y[10] = 10
print(y)

# popitem() of a big dict, item by item
big: dict[int, int] = {}
for i in range(1000):
    big[i * 7919 % 1000] = i
total = 0
last = -1
while big:
    k3, v3 = big.popitem()
    total += k3 * v3
    last = k3
print(total, last, len(big))
for i in range(20):
    big[i] = i
print(big.popitem(), len(big))

# popitem() and inserts of new keys in turn, well past the table's size: the entries popitem
# cuts off still fill the table until it is rebuilt (CPython keeps dk_usable), so lookups end
d2 = {"a": 1}
for j in range(1000):
    d2.popitem()
    d2[str(j)] = j
print(d2, "a" in d2, d2.get("zz"))
n2 = {0: 0, 1: 1}
for j in range(1, 5000):
    n2.popitem()
    n2[j * 37] = j
print(n2, n2.copy(), dict(n2), list(reversed(n2)), 37 in n2)
# where the table is rebuilt decides what a loop that replaces keys sees, as in CPython
for size in range(1, 12):
    churn: dict[int, int] = {}
    for j in range(size):
        churn[j] = j
    for j in range(size):
        churn.popitem()
        churn[100 + j] = j
    seen: list[int] = []
    try:
        for k4 in churn:
            seen.append(k4)
            del churn[k4]
            churn[k4 + 1000] = k4
    except RuntimeError as e:
        print(size, "RuntimeError", e, seen)
    else:
        print(size, seen, churn)
