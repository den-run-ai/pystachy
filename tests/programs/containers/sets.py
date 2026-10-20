# sets and frozensets: CPython's tables (runtime.c), so that ints, bools and tuples of them
# iterate and print in CPython's order; strs are sorted first (CPython's order of them depends
# on PYTHONHASHSEED)
from typing import Optional


def show(s: set[int]) -> str:
    return f"{s} {len(s)} {bool(s)}"


# displays: the items inserted in order; one of more than two constants is CPython's frozenset
# constant merged into a new set, and a for loop over one iterates that frozenset
a = 100
print({3, 1, 2}, {a, 1, 17, 33, 49}, {100, 1, 17, 33, 49})
for x in {100, 1, 17, 33, 49}:
    print(x, end=" ")
print()
print([x for x in {8, 20, 33620, 21, -2, 4338179527542382004}])
print({-1, -2, 2**61 - 1, 2**61, -9223372036854775808, 9223372036854775807})
print({(1, 2), (2, 1), (0, 0)}, {(1, (True, False)), (2, (False, True))})
e: set[int] = set()
f: frozenset[int] = frozenset()
print(e, f, frozenset({3, 1, 2}), [{1, 2}, {3}], {"k": {5, 4}}, ({1}, frozenset({2})))

# constructors
print(set([5, 3, 5, 1]), set((9, 8, 9)), set(range(10, 0, -3)), frozenset(x * x for x in range(5)))
d = {7: "a", 3: "b", 15: "c"}
print(set(d), frozenset(d), sorted(set("hello")), len(frozenset("hello")))
s = {1, 2, 3}
t = set(s)
print(t, t is s, t == s)
fz = frozenset(s)
print(frozenset(fz) is fz, fz.copy() is fz, s.copy() is s)

# methods
s.add(4)
s.add(2)
s.discard(10)
s.discard(1)
s.remove(2)
print(show(s))
try:
    s.remove(99)
except KeyError as k:
    print("KeyError", k)
empty: set[int] = set()
try:
    empty.pop()
except KeyError as k:
    print("KeyError", k)
p = {5, 6, 7}
print(p.pop(), p.pop(), p)
p.clear()
print(p, len(p))
u = {1, 2, 3}
u.update([3, 4], {5}, d)
print(u)
print(u.union([20, 1]), u.union(), u.intersection([2, 3, 99]), u.intersection({1, 15}, [15]))
print(u.difference({1, 2}), u.difference([3], {4}), u.symmetric_difference({1, 100}), u.symmetric_difference([1, 101]))
v = {1, 2, 3, 4}
v.difference_update([1], {2})
print(v)
v.intersection_update({3, 4, 5})
print(v)
v.symmetric_difference_update([4, 6])
print(v)
print({1, 2}.issubset([1, 2, 3]), {1, 2}.issubset({1}), {1, 2, 3}.issuperset([3]), {1}.isdisjoint([2]), {1}.isdisjoint({1}))

# operators
a1 = {1, 2, 3, 4}
b1 = frozenset({3, 4, 5})
print(a1 | b1, a1 & b1, a1 - b1, a1 ^ b1)
print(b1 | a1, b1 & a1, b1 - a1, b1 ^ a1)
print(a1 < b1, a1 <= a1, {3, 4} < b1, b1 > {3}, b1 >= b1, a1 == {4, 3, 2, 1}, a1 != a1, b1 == {3, 4, 5})
c1 = a1
c1 |= {10}
c1 &= {1, 2, 10, 11}
c1 -= {2}
c1 ^= {1, 7}
print(c1, a1, c1 is a1)
g1 = b1
g1 |= {9}
print(g1, b1, g1 is b1)
print(3 in a1, 3 not in b1, (1, 2) in {(1, 2)}, True in {1})

# iteration, consumers
total = 0
for x in {5, 10, 15}:
    total += x
print(total, sorted({3, 1, 2}), min({4, 2, 8}), max({4, 2, 8}), sum({1, 2, 3}), list({30, 10, 20}))
print(any(x > 2 for x in {1, 2, 3}), all({1, 2}), {x % 3 for x in range(10)}, {(x, x * x) for x in range(3)})
for i, x in enumerate({7, 9}):
    print(i, x)
w = {1, 2, 3}
try:
    for x in w:
        w.add(x + 10)
except RuntimeError as r:
    print("RuntimeError", r)

# an empty set takes the type its first use shows
seen = set()
for x in [3, 1, 3, 2, 1]:
    if x not in seen:
        seen.add(x)
print(seen)
words = set()
words.update(["b", "a", "b"])
print(sorted(words))
graph = {}
for x, y in [(1, 2), (1, 3), (2, 3)]:
    graph.setdefault(x, set()).add(y)
print(graph)
acc = set()
acc |= {(1, "x")}
print(acc)


# sets as parameters, results, fields and optional values
def evens(xs: list[int]) -> set[int]:
    return {x for x in xs if x % 2 == 0}


class Bag:
    def __init__(self) -> None:
        self.items: set[str] = set()

    def put(self, x: str) -> None:
        self.items.add(x)


bag = Bag()
bag.put("x")
bag.put("x")
print(evens([1, 2, 3, 4]), len(bag.items))
maybe: Optional[set[int]] = None
print(maybe is None)
maybe = {1}
if maybe is not None:
    print(maybe, 1 in maybe)
add = maybe.add
add(2)
print(maybe, isinstance(maybe, set), isinstance(maybe, frozenset), isinstance(fz, frozenset))
pairs: set[tuple[int, Optional[str]]] = {(1, None), (1, "a")}
print(len(pairs), (1, None) in pairs, (2, None) in pairs)

# a bool where the elements are ints is the int it equals; remove()'s KeyError names the bool
ints = {1, 2}
ints.remove(True)
ints.discard(False)
try:
    ints.remove(True)
except KeyError as k:
    print("KeyError", k)
print(f"{ints} {ints!r}", str(frozenset(ints)), True in ints, 2.0 in [x for x in ints])
