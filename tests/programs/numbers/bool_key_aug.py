# d[k] op= v of a bool key where the dict's keys are ints (also as a tuple key's item): it finds
# the int key it equals, whose value it sets (the key stays the int), and a key it does not find
# raises CPython's KeyError, naming the bool. A bool | None key gets and tests (in) the int key
# it equals; None is in no dict.
d: dict[int, int] = {1: 5, 0: 2}
d[True] += 1
d[False] -= 1
d[True] *= 3
n = 2
d[True] += n * 2 + len("ab")
print(d)
if True in d:
    d[True] += 1
print(d)
try:
    e: dict[int, int] = {}
    e[True] += 1
except KeyError as x:
    print("KeyError", x, repr(x))
t: dict[tuple[int, str], int] = {(1, "a"): 4}
t[(True, "a")] -= 1
print(t)
try:
    t[(True, "b")] += 1
except KeyError as x:
    print("KeyError", x)
names: dict[int, str] = {1: "one", 0: "zero"}
for b in [True, False, None]:
    k: bool | None = b
    print(names.get(k), names.get(k, "dflt"), k in names, k not in names)
