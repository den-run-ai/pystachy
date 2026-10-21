# dict.popitem(): the last item, removed; the entries after it are dropped (CPython's
# dk_nentries), which insertions, loops, reversed() and copies that follow must see, as must a
# loop that it changes the dict under. (tests/programs/containers/dict_popitem.py has inserts after popitem() and the
# points where the table is rebuilt.)
d = {"a": 1, "b": 2, "c": 3}
print(d.popitem(), d, len(d))
d["d"] = 4
print(d, list(reversed(d)), d.popitem(), d.popitem(), d)
d["e"] = 5
d["a"] = 10
print(d, d.popitem(), d)
try:
    d.popitem()
    d.popitem()
except KeyError as e:
    print("KeyError", e, repr(e), d)

# holes before the last entry, from deletions, are dropped with it
h: dict[int, int] = {}
for i in range(10):
    h[i] = i * i
for i in range(3, 9):
    del h[i]
print(h.popitem(), h, list(h), list(reversed(h)), h.copy(), dict(h))
h[100] = 1
print(h, h.popitem(), h.popitem(), h)

# other key and value types
f = {(1, "p"): 0.5, (2, "q"): 1.5}
print(f.popitem(), f)
o: dict[str, int | None] = {"n": None, "s": 7}
print(o.popitem(), o.popitem(), o)
u: dict[int, int | str] = {1: "one", 2: 2}
k, v = u.popitem()
print(k, v, u)
lists = {"x": [1, 2], "y": [3]}
key, items = lists.popitem()
items.append(4)
print(key, items, lists)
nested = {"outer": {"inner": [1]}}
print(nested.popitem(), nested)
uni = {"ω": 1, "é": 2}
print(uni.popitem(), uni)

# a loop over a dict that popitem() changes raises CPython's RuntimeError
g = {"p": 1, "q": 2, "r": 3}
try:
    for k2 in g:
        print("loop", k2, g.popitem())
except RuntimeError as e:
    print("RuntimeError", e, g)
g2 = {"p": 1, "q": 2, "r": 3}
try:
    for k3 in reversed(g2):
        print("reversed", k3, g2.popitem())
except RuntimeError as e:
    print("RuntimeError", e, g2)

# emptying a large dict, in a function, and by a method of a field
big: dict[int, str] = {}
for i in range(100000):
    big[i] = str(i)
total = 0
while big:
    total += int(big.popitem()[1])
print(total, len(big), big)


def drain(m: dict[str, int]) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    while m:
        out.append(m.popitem())
    return out


class Stack:
    def __init__(self) -> None:
        self.items: dict[str, int] = {}

    def push(self, k: str, v: int) -> None:
        self.items[k] = v

    def pop(self) -> tuple[str, int]:
        return self.items.popitem()


print(drain({"x": 1, "y": 2, "z": 3}), drain({}))
s = Stack()
s.push("a", 1)
s.push("b", 2)
s.push("a", 3)
print(s.pop(), s.pop(), s.items)
try:
    s.pop()
except KeyError as e:
    print("KeyError", e)

