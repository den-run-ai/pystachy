d = {"one": 1, "two": 2, "three": 3}
d["four"] = 4
d["two"] = 22
print(d, len(d), d["one"], "two" in d, "five" in d, d.get("five", -1), d.get("one", -1))
for k in d:
    print(k, end=" ")
print()
for k, v in d.items():
    print(k, v, end=" | ")
print()
print(list(d.keys()), list(d.values()), list(d.items()))
print(d.pop("one"), d)
del d["three"]
print(d, d.setdefault("x", 10), d.setdefault("x", 20), d)
e = d.copy()
e["y"] = 1
print(len(d), len(e), d == e, d == d.copy(), {"a": 1, "b": 2} == {"b": 2, "a": 1})
sq: dict[int, int] = {}
for i in range(-5, 6):
    sq[i * 7] = i * i
print(sq, sq[-35], sq[0], 14 in sq, 15 in sq)
for i in range(1000):
    sq[i] = i
for i in range(0, 1000, 2):
    del sq[i]
print(len(sq), sq[999], sq[-35], 998 in sq, list(sq.keys())[:5])
memo: dict[int, int] = {}


def fib(n: int) -> int:
    if n < 2:
        return n
    if n in memo:
        return memo[n]
    r = fib(n - 1) + fib(n - 2)
    memo[n] = r
    return r


print(fib(80), len(memo))
groups: dict[str, list[str]] = {}
for w in ["apple", "avocado", "banana", "blueberry", "cherry", "apricot"]:
    k = w[0]
    if k not in groups:
        groups[k] = []
    groups[k].append(w)
print(groups)
inv: dict[int, str] = {}
for name, num in {"a": 1, "b": 2}.items():
    inv[num] = name
print(inv, {1: 1.5, 2: 2.5}, {"k": [1, 2]}, {"t": True})
counts = {"x": 0}
counts["x"] += 5
counts["x"] *= 3
print(counts)
e.clear()
print(e, len(e), bool(e), bool(counts))
nested: dict[str, dict[str, int]] = {"outer": {"inner": 1}}
nested["outer"]["inner2"] = 2
print(nested, nested["outer"]["inner2"])
