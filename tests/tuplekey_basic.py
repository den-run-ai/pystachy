# Dicts keyed by tuples of int, bool, str and str | None items (and of such tuples): equal
# tuples are one key, iteration is in insertion order, and repr, ==, KeyError show the tuples.
sources: dict[tuple[str, str | None], int] = {}
names: list[str | None] = [None, "x", "y"]
n = 0
for s in ["a", "b"]:
    for nm in names:
        sources[s, nm] = n
        n += 1
print(sources, len(sources))
print(sources[("a", None)], sources["b", "y"], ("a", "x") in sources, ("c", None) in sources, ("a", "z") not in sources)
print(sources.get(("b", None), -1), sources.get(("q", None), -1), sources.pop(("b", "x")), sources.pop(("q", "q"), 99))
key = ("a", "y")
sources[key] += 10
del sources["a", None]
print(sources, sorted([k for k in sources if k[1] is not None]), list(sources)[0])
for (s, nm), v in sources.items():
    print(s, nm, v, (s, nm) in sources)
for k in reversed(sources):
    print(k, sources[k])
flags = {}
flags[1, True] = "one"
flags[2, False] = "two"
flags[1, True] = "uno"
print(flags, flags[(1, True)], (1, False) in flags)
nested: dict[tuple[int, tuple[str, str]], list[int]] = {(1, ("a", "b")): [1]}
nested[(1, ("a", "b"))].append(2)
nested.setdefault((2, ("c", "d")), []).append(3)
print(nested, nested == {(2, ("c", "d")): [3], (1, ("a", "b")): [1, 2]}, nested != dict(nested), nested.copy())
got = nested.get((2, ("c", "d")))
print(got, nested.get((3, ("c", "d"))), max(nested), min(nested.keys()))
grid: dict[tuple[int, int], int] = {}
for i in range(2000):
    grid[i, i * 7 - 1000] = i
for i in range(0, 2000, 2):
    del grid[i, i * 7 - 1000]
total = 0
for i in range(1, 2000, 2):
    total += grid[i, i * 7 - 1000]
print(total, len(grid), grid.get((5, -965), 0), grid.get((4, -972), 0))
words: dict[tuple[str, int], str | None] = {("w", 1): None}
words[("w", 2)] = "two"
print(words, words[("w", 1)] is None, words.get(("w", 3), "?"))
print(sources["zz", None])
