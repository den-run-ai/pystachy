# a | b of two dicts of one type: a new dict, a copy of a (dict.copy()) updated with b, so b's
# value wins for a key both hold and keeps a's position; a |= b updates a in place, from a dict
# of its type or a list of (key, value) tuples, as a.update(b) does. None on the left of |=
# raises CPython's TypeError, and a None right operand of |= is not iterable.
from typing import Callable

a = {"x": 1, "y": 2}
b = {"y": 3, "z": 4}
c = a | b
print(c, b | a, a, b, c is a, a | {}, {} | a, a | a)
e: dict[str, int] = {}
print(e | e, e | b, (a | b) | {"w": 0}, a | b | {"x": -1})
a |= b
print(a)
a |= [("w", 0), ("x", 10), ("w", 5)]
print(a)
a |= a
a |= {}
print(a, len(a))
alias = a
alias |= {"n": 1}
print(a is alias, a)

# keys that are tuples, values that may be None, non-ASCII strs
t = {(1, "a"): None, (2, "b"): 2.5}
t2: dict[tuple[int, str], float | None] = {(2, "b"): None, (3, "é"): 3.5}
print(t | t2, t2 | t)
t |= t2
print(t)
u = {"café": "été"} | {"日本": "語", "café": "x"}
print(u)


# targets: a field, an item, a global in a function, a closure's variable
class Box:
    def __init__(self) -> None:
        self.d: dict[str, int] = {"k": 0}

    def merge(self, other: dict[str, int]) -> dict[str, int]:
        self.d |= other
        return self.d | {"tmp": -1}


bx = Box()
print(bx.merge({"a": 1}), bx.d)
bx.d |= {"k": 5}
print(bx.d)
nested = {"outer": {"i": 1}}
nested["outer"] |= {"j": 2}
print(nested)
g = {1: "one"}


def add_two() -> None:
    global g
    g |= {2: "two"}


add_two()
print(g)


def collector() -> Callable[[int], dict[int, int]]:
    seen: dict[int, int] = {}

    def add(k: int) -> dict[int, int]:
        nonlocal seen
        seen |= {k: k * k}
        return seen
    return add


f = collector()
f(3)
print(f(4))

# None
n: dict[str, int] | None = None
try:
    n |= {"a": 1}
except TypeError as ex:
    print("TypeError", ex)
m: dict[str, int] | None = None
try:
    n |= m
except TypeError as ex:
    print("TypeError", ex)
d2 = {"a": 1}
try:
    d2 |= m
except TypeError as ex:
    print("TypeError", ex)
o: dict[str, int] | None = {"p": 1}
o |= {"q": 2}
print(o)


# evaluation order: the left operand, then the right, then the merge
def side(tag: str, d: dict[str, int]) -> dict[str, int]:
    print("eval", tag)
    return d


print(side("left", {"a": 1}) | side("right", {"b": 2}))
h = {"a": 1}
h |= side("rhs", {"a": 2})
print(h)

# the result's table is a copy's, then a merge's, as CPython makes it: what a loop that changes
# it sees
big: dict[int, int] = {}
for i in range(12):
    big[i] = i
for i in range(8):
    del big[i]
r = big | {100: 0}
seen: list[int] = []
for k in r:
    seen.append(k)
    if k == 8:
        del r[9]
        r[200] = 0
print(seen, r)
