# lib/collections: Pystachy's deque, a generic class, against CPython's (Modules/_collectionsmodule.c).
# Cases after CPython's Lib/test/test_deque.py.
from collections import deque

d = deque([1, 2, 3])
d.append(4)
d.appendleft(0)
print(d, len(d), d[0], d[-1], d.pop(), d.popleft(), d)
q: deque[int] = deque()
for i in range(10):
    q.append(i)
    if i % 3 == 0:
        q.popleft()
print(q, list(q), [x * 2 for x in q], sum(q), 5 in q, 0 in q)
w = deque("abc", maxlen=3)
w.append("d")
print(w, w.maxlen, deque([1.5], maxlen=2))
r = deque([1, 2, 3, 4, 5])
r.rotate(2)
print(r)
r.rotate(-3)
print(r)
r.reverse()
print(r, r.count(3), r.index(3), r.index(2, 1))
r.insert(1, 9)
r.remove(3)
r[0] = 7
del r[1]
print(r, bool(r), bool(deque[int]()))
e = deque([1, 2])
e.extend(e)
e.extendleft([7, 8])
print(e, e.copy(), e == e.copy(), e < deque([9]), e + deque([5]), e * 2)
e += [6]
e *= 2
print(e)
for args in [(-1,)]:
    try:
        deque([1], -1)
    except ValueError as ex:
        print("ValueError:", ex)
z: deque[str] = deque()
try:
    z.pop()
except IndexError as ex:
    print("IndexError:", ex)
try:
    z.popleft()
except IndexError as ex:
    print("IndexError:", ex)
try:
    print(d[10])
except IndexError as ex:
    print("IndexError:", ex)
try:
    d.remove(99)
except ValueError as ex:
    print("ValueError:", ex)
try:
    deque([1, 2], maxlen=2).insert(0, 5)
except IndexError as ex:
    print("IndexError:", ex)
m: deque[int] = deque([0], maxlen=3)
for i in range(1, 8):
    m.append(i)
    m.appendleft(-i)
print(m, deque([1, 2, 3], maxlen=5) * 3, deque[int]([], maxlen=0), deque(list(range(4)), 0))


# a deque in a field, a parameter and a return, typed deque[T]
class Window:
    def __init__(self, size: int) -> None:
        self.recent: deque[str] = deque(maxlen=size)
        self.seen: deque[int] = deque()

    def add(self, word: str) -> None:
        self.recent.append(word)
        self.seen.appendleft(len(word))


def drain(q: deque[int]) -> deque[int]:
    out: deque[int] = deque()
    while q:
        out.appendleft(q.popleft())
    return out


win = Window(3)
for word in "the quick brown fox jumps".split():
    win.add(word)
print(win.recent, win.seen, drain(deque([1, 2, 3])), drain(win.seen), win.seen)

# a long steady-state queue and a big stack, at both ends (amortized O(1) pops)
s1 = deque(list(range(100)))
for i in range(100000):
    s1.append(s1.popleft())
print(s1[0], s1[-1], len(s1))
s2: deque[int] = deque()
for i in range(10000):
    s2.appendleft(i)
total = 0
while s2:
    total += s2.pop()
    if s2:
        total -= s2.popleft()
print(total)
s3 = deque(list(range(10)))
for i in range(25):
    s3.rotate(i - 12)
    s3.insert(i % 7, -i)
    del s3[(i * 3) % len(s3)]
print(s3, s3.index(-24), s3.count(-1), -3 in s3, s3 == deque(list(s3)), s3 != s3.copy(), s3 >= s3)
print(deque(["b", "a"]) < deque(["b", "a", "c"]), deque([2]) > deque([1, 9]), deque([1]) <= deque([1]))


# in, count(), index() and remove() compare from the left, an item with the value looked for
# (item == x), and an item that is the value is equal to it without a call of __eq__: also where
# appendleft() and a popleft() that takes half of the right items hold them in the left list
log: list[str] = []


class Eq:
    def __init__(self, v: int, tag: str) -> None:
        self.v = v
        self.tag = tag

    def __eq__(self, other: "Eq") -> bool:
        log.append(f"{self.tag}={other.tag}")
        return self.v == other.v

    def __repr__(self) -> str:
        return self.tag


eqs = deque([Eq(3, "c"), Eq(4, "d")])
eqs.appendleft(Eq(2, "b"))
eqs.appendleft(Eq(1, "a"))
c = eqs[2]
for look in [Eq(4, "x"), Eq(9, "y"), c]:
    log.clear()
    print(eqs, look in eqs, eqs.count(look), " ".join(log))
log.clear()
print(eqs.index(c), eqs.index(Eq(2, "z"), 1), eqs.index(c, -2, 3), " ".join(log))
log.clear()
try:
    eqs.index(c, 3)
except ValueError as err:
    print("ValueError", err, " ".join(log))
log.clear()
eqs.remove(c)
print(eqs, " ".join(log))
log.clear()
try:
    eqs.remove(Eq(7, "w"))
except ValueError as err:
    print("ValueError", err, " ".join(log))
f = deque([Eq(i, "pqrst"[i - 1]) for i in range(1, 6)])
f.popleft()
log.clear()
print(f, Eq(5, "u") in f, f.count(f[1]), f.index(f[2]), " ".join(log))

# CPython checks the total repeated length even for bounded deques, before mutation.
for multiple in [4611686018427387903, 4611686018427387904, 9223372036854775807]:
    bounded = deque([1, 2], maxlen=3)
    try:
        print(bounded * multiple)
    except MemoryError:
        print("MemoryError", bounded)
    try:
        bounded *= multiple
        print(bounded)
    except MemoryError:
        print("MemoryError", bounded)
