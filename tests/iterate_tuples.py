# tuples of one item type in for loops, comprehensions and str.join(); join() over strings and dicts
for x in (1, 2, 3):
    print(x)
for i, s in enumerate(("a", "b")):
    print(i, s)
for a, b in zip((1, 2), [3, 4]):
    print(a, b)
print(" ".join("abc"), "-".join({"x": 1, "y": 2}), "+".join(("p", "q")))
print([c for c in ("u", "v")], sum(n for n in (4, 5)))
for n in sorted(range(3)):
    print(n)
for y in list(enumerate(["a"])):
    print(y)
zs: list[int] = []
zs.extend(range(3))
print(zs)
