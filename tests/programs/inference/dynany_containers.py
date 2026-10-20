# pystachy: dynamic-any
# list[Any], dict[Any, Any] and tuples of Any values: displays that flow into Any storage hold
# boxes from the start, so every alias may store any value; numeric keys that are equal are one
# key; cycles print as CPython prints them.
from typing import Any

xs: list[Any] = [1, "two", 3.0]
xs.append([4, 5])
xs.append({"six": 6})
xs.insert(0, None)
print(xs, len(xs))
print(xs.pop(), xs)
print(xs.index("two"), xs.count(3), 3 in xs, "nope" in xs)
alias: Any = xs
alias.append("via alias")
print(xs)
alias[0] = "zero"
print(xs[0], alias[-1], alias[1])
del alias[1]
print(xs)
d: dict[Any, Any] = {}
d[1] = "int one"
d[1.0] = "float one"
d[True] = "bool one"
d["k"] = [1, 2]
d[(1, "t")] = "tuple"
d[None] = 0
print(d, len(d))
print(d[1], d[(1, "t")], d.get("missing"), d.get("k"))
for k in d:
    print(repr(k), "->", repr(d[k]))
for k, v in d.items():
    print(k, v)
inner: Any = d["k"]
inner.append(3)
print(d["k"])
dd: Any = d
print(dd.get(None), dd.pop(None), len(dd))
cyc: list[Any] = [1]
cyc.append(cyc)
print(cyc)
cd: dict[Any, Any] = {"self": None}
cd["self"] = cd
print(cd)
t: Any = (1, "a", [2])
print(t, t[2], len(t), t + (3,), t * 2)
a, b, c = t
print(a, b, c)
nested: Any = [[1, 2], {"a": [3, {"b": 4}]}]
print(nested[1]["a"][1]["b"])
nested[1]["a"][1]["b"] = "changed"
print(nested)
print([1, "a"] == [1, "a"], [1, 2.0] == [1, 2], {"a": 1} == {"a": 1.0}, [1, [2]] < [1, [3]])
ys: list[Any] = [3, 1.5, 2, True]
ys.sort()
print(ys)
print(sorted([3, 1.5, 2]))
s: Any = "hello world"
print(s.upper(), s.split(" "), s.replace("o", "0"), len(s), s[1], s.startswith("he"))
words: Any = s.split(" ")
words.append("!")
print(words, " ".join(words))
