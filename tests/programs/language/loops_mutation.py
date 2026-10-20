# Loops that change what they iterate over behave like CPython's iterators: a list is read
# at its current length, reversed() counts down from the length it started with, and dicts
# fail when their size changes (see dict_changed_size.py and dict_keys_changed.py).


def evens_removed(xs: list[int]) -> list[int]:
    for x in reversed(xs):
        if x % 2 == 0:
            xs.remove(x)
    return xs


print(evens_removed([2, 4, 1, 6]))
ys = [1, 2, 3]
for y in reversed(ys):
    print(y, end=" ")
    if len(ys) < 5:
        ys.append(0)
print(ys)
zs = [1, 2, 3, 4, 5]
for z in reversed(zs):
    zs.pop()
    zs.pop()
    print(z, zs)
grow = [1]
for g in grow:
    if g < 5:
        grow.append(g + 1)
print(grow)

# a dict whose size stays the same: positions follow CPython's table layout
d = {"a": 1, "b": 2, "c": 3}
for k in d:
    d[k] = d.pop(k)
    print(k, end=" ")
print(d)
e = {1: 10, 2: 20}
for k2 in e:
    e[k2] = e[k2] + 1
print(e)
r = {1: 1, 2: 2, 3: 3}
for k3 in reversed(r):
    r[k3] = k3 * 10
print(r, list(reversed(r)))

# deleting is O(1): this would take minutes with a table rebuilt per deletion
big: dict[int, int] = {}
for i in range(200000):
    big[i] = i
for i in range(0, 200000, 2):
    del big[i]
print(len(big), sum(big.values()), list(big)[:3])
for i in range(200000):
    big[i] = -i
print(len(big), list(big)[:3], list(big)[-3:])
s: dict[str, int] = {}
for i in range(3000):
    s[str(i)] = i
    if i % 3 == 0 and str(i // 2) in s:
        del s[str(i // 2)]
print(len(s), sum(s.values()), list(s)[:5], list(s)[-5:])
c = s.copy()
c["new"] = 1
print(len(c), len(s), c == s, list(c)[-2:])
s.clear()
s["x"] = 1
print(s, c["2999"], c.get("0", -5), c.pop("nope", -1))

# reversed(range(...)), zip of one sequence, list targets
for i in reversed(range(4)):
    print(i, end=" ")
print()
for i in reversed(range(10, -10, -3)):
    print(i, end=" ")
print()
for i in reversed(range(5, 5)):
    print("never")
for i in reversed(range(-9223372036854775807 - 1, 9223372036854775807, 4611686018427387904)):
    print(i)
for t in zip([1, 2]):
    print(t)
for a, b in zip("ab", [1, 2, 3]):
    print(a, b)
for [p, q] in [(1, 2), (3, 4)]:
    print(p + q)
[u, [v, w]] = [5, [6, 7]]
print(u, v, w)
