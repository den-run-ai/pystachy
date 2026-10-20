# range() as a value: an object that is assigned, passed, returned and stored, which loops,
# comprehensions and consumers step through as they do through range(...) itself
import bisect
import codecs
import heapq
import random
from collections import Counter, deque
from dataclasses import dataclass
from typing import NamedTuple

MIN = -9223372036854775807 - 1
MAX = 9223372036854775807


def make(n: int) -> range:
    return range(n, 0, -2)


def total(r: range) -> int:
    s = 0
    for x in r:
        s += x
    return s


def first(r) -> int:
    return r[0]


def squares(r: range):
    for x in r:
        yield x * x


@dataclass
class Span:
    name: str
    r: range


class P(NamedTuple):
    r: range
    k: int


class Holder:
    def __init__(self, n: int) -> None:
        self.r = range(n)
        self.rs: list[range] = []

    def add(self, r: range) -> None:
        self.rs.append(r)

    def total(self) -> int:
        return sum(len(x) for x in self.rs) + len(self.r)


# the three forms, repr() and str(), the attributes
r = range(10)
print(r, len(r), r.start, r.stop, r.step)
print(range(0, 10, 2), str(range(5, 1, -1)), repr(range(3)), range(-3), range(2, -2), range(4, 4, -1))
print(f"{r!r} {r}", "%r %s" % (r, r), "{}".format(range(1, 9, 3)), format(r, ""), [r], (r,))

# loops and comprehensions
for i in r:
    print(i, end=" ")
print()
for i in reversed(range(1, 10, 3)):
    print(i, end=" ")
print()
for k, i in enumerate(range(3, 0, -1)):
    print(k, i, end="; ")
print()
for a, b in zip(range(3), r):
    print(a, b, end="; ")
print()
for k, i in enumerate(r, 5):
    if k > 7:
        break
    print(k, i, end="; ")
print()
print([x * 2 for x in r if x % 3 == 0], {i: i for i in range(3)}, {x % 3 for x in r})
print([y for x in range(3) for y in range(x)], list(x for x in range(3)), list(squares(range(4))))
g = (x * x for x in range(4))
print(sum(g), sum(x for x in range(5)))

# consumers
print(list(r), tuple(range(3)), sorted(r, reverse=True), sum(r), sum(range(5), 10), min(r), max(r))
print(any(r), all(r), any(range(1)), all(range(1, 3)), any(range(0)), all(range(0)))
print(set(range(4)), frozenset(range(2)), bytes(range(3)), list(reversed(range(5, -5, -3))))
print(max(r, key=lambda x: -x), min(r, key=lambda x: x % 4), sorted(range(6), key=lambda x: (x % 3, -x)))
print(",".join(str(i) for i in range(4)), ",".join(map(str, range(3, 0, -1))), list(map(lambda x: x * 2, r)))
print(list(filter(None, range(-1, 2))), dict(zip(range(3), range(10, 13))), list(enumerate(range(2), 1)))
xs = [9, 9, 9, 9]
xs[1:3] = range(2)
xs.extend(range(2))
a, b, c = range(3)
head, *rest = range(4)
print(xs, a, b, c, head, rest, *range(4), [*range(2), *range(3)])
it = iter(range(2, 5))
print(next(it), next(it), next(it), next(it, -1))
for x in iter(range(3)):
    print(x, end=";")
print()

# len(), bool(), in, indexing, slicing
print(3 in r, 10 in r, -1 not in r, True in r, False in range(1), -1 in range(0, -10, -1))
none: int | None = None
print(none in r, r[0], r[-1], r[5], bool(r), bool(range(0)), not range(5, 5))
if range(2, 2):
    print("non-empty")
else:
    print("empty")
q = range(-5, 20, 4)
print(q.index(15), q.index(-5), q.count(7), q.count(8), len(range(10, 0, -3)), len(range(0, 10, -1)))
for s in [range(10), range(0, 10, 3), range(10, 0, -2), range(0), range(5, 5), range(-3, 4)]:
    print(s[:], s[::-1], s[1:], s[:-1], s[2:5], s[::2], s[::-2], s[-3:], s[5:1:-1], s[100:], s[-100:2])
    print(s[1:-1:3], s[None:None:None], s[True:], len(s[::3]))
lo: int | None = None
print(range(10)[lo:3], range(10)[lo:lo:lo], range(MIN, 0)[1:], range(0, MAX)[::-1])

# ==, !=, hash, containers of ranges
print(range(0) == range(5, 5), range(0, 3) == range(0, 3, 1), range(0, 10, 2) != range(0, 9, 2))
print(range(1, 2) == range(1, 5, 9), range(1, 2) == range(2, 3), r == r, r != range(10))
print(hash(range(0)), hash(range(1, 2)), hash(range(0, 10, 3)), hash(range(5, 5)) == hash(range(0)))
d = {range(3): "a", range(0, 3, 1): "b", range(0): "c", range(4, 4): "d"}
print(d, len(d), range(0, 3) in d, {range(2), range(0, 2), range(1)})
print(range(3) in [range(0, 3)], [range(3)] == [range(0, 3)], (range(1), 2) == (range(0, 1), 2))
n: range | None = None
print(n is None, n == range(0), range(0) == n, r is range(10))

# passed, returned and stored
rs = [range(3), range(1, 4), make(7)]
print(rs, total(make(9)), first(range(5, 9)))
span = Span("a", range(4))
print(span, span == Span("a", range(0, 4)), P(range(1, 2), 3), P(range(3), 1).r)
h = Holder(3)
h.add(range(5))
h.add(q)
print(h.total(), h.r, h.rs)
f = lambda k: range(k, -1, -1)
print(f(3), list(f(2)), [list(range(i)) for i in range(3)])
m = codecs.make_identity_dict(range(256))
m.update({0x80: 0xC7, 0x81: 0xFC})
print(len(m), m[65], m[0x80], m[255], sorted(m.items())[126:130])
random.seed(1)
print(random.sample(range(100), 3), random.choice(range(5, 50, 5)), deque(range(3)), deque(r, 2))
print(Counter([x % 3 for x in r]), Counter(range(3)), heapq.nlargest(2, r), bisect.bisect(range(0, 100, 10), 35))

# type(), isinstance()
print(type(r).__name__, type(r).__module__, type(r) is range, type(range(1)) == type(r))
print(isinstance(r, range), isinstance(5, range), isinstance(r, (int, range)), isinstance(r, object))

# counts of 2**63 or more, and the ends of int
big = range(MIN, MAX)
print(bool(big), big[0], big[-1], big[2**62], big[-2**62], 0 in big, MAX in big, big[MAX], big[MIN])
print(big.index(MIN + 5), big.count(MIN), big[-1:-4:-1], big[5:2:-1], big[-3:], big[:-5:4][:2])
print(big[MIN:MAX:MAX], range(MIN, 0)[:], range(MIN, 0)[-2:], range(0, MIN, -1)[1:3])
print(hash(big), hash(range(MIN, MAX, 3)), hash(range(MAX, MIN, -1)), hash(range(MAX, MIN, -2)))
print(range(MAX, MIN, -1)[MIN], range(MIN, MAX, 2)[-1], range(MIN, MAX - 1, 2)[5:9], range(MIN + 3, MAX, 3)[::-1])
print(sum(1 for _ in range(MAX - 3, MAX)), list(range(MIN, MIN + 3)), list(range(MAX, MAX - 3, -1)))
try:
    print(len(big))
except OverflowError as ex:
    print("OverflowError", ex)

# errors
try:
    print(range(1, 2, 0))
except ValueError as ex:
    print("ValueError", ex)
for i in [5, -6, MAX, MIN]:
    try:
        print(range(5)[i])
    except IndexError as ex:
        print("IndexError", ex)
try:
    print(range(0, 10, 3).index(4))
except ValueError as ex:
    print("ValueError", ex)
try:
    print(range(3)[::0])
except ValueError as ex:
    print("ValueError", ex)
try:
    print(sorted([range(3), range(2)]))
except TypeError as ex:
    print("TypeError", ex)
try:
    print(min(range(4, 4)))
except ValueError as ex:
    print("ValueError", ex)
for s in [range(3), range(1), range(MIN, MAX)]:
    try:
        x, y = s
        print(x, y)
    except ValueError as ex:
        print("ValueError", ex)
print(range(0, 10, 0))
