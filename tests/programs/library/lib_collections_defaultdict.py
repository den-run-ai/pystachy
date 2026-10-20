# lib/collections: defaultdict, a generic class over a dict, against CPython's C type
# (Modules/_collectionsmodule.c): factories (builtin types, functions, lambdas, None), the dict
# methods that do not call the factory, copies, | and the repr.
from collections import Counter, OrderedDict, defaultdict
from typing import Callable

# factories: builtin types, defs, lambdas, None
ints: defaultdict[str, int] = defaultdict(int)
for w in "a b a c a ω é ω".split():
    ints[w] += 1
print(ints, ints["zz"], ints)
lists: defaultdict[str, list[int]] = defaultdict(list)
for i, w in enumerate("x y x z".split()):
    lists[w].append(i)
print(lists, lists.default_factory is not None)
sets: defaultdict[int, set[str]] = defaultdict(set)
sets[1].add("p")
sets[1].add("q")
sets[2]
print(sorted(sets[1]), len(sets), sorted(sets))
strs: defaultdict[str, str] = defaultdict(str)
strs["k"] += "v"
strs["k"] += "w"
print(strs)
floats: defaultdict[str, float] = defaultdict(float)
floats["f"] += 0.5
print(floats)
bools: defaultdict[str, bool] = defaultdict(bool)
print(bools["b"], bools)
dicts: defaultdict[str, dict[str, int]] = defaultdict(dict)
dicts["outer"]["inner"] = 1
print(dicts)
nested: defaultdict[str, list[str]] = defaultdict(list, {"a": ["x"]})
nested["a"].append("y")
nested["b"].append("z")
print(nested)
pairs: defaultdict[str, int] = defaultdict(int, [("p", 1), ("q", 2)])
ordered = defaultdict(int, OrderedDict([("o", 5)]))
copied = defaultdict(list, nested)
copied["c"].append("w")
print(pairs, ordered, copied, nested)


def zero() -> int:
    return 0


def seven():
    return 7


z: defaultdict[str, int] = defaultdict(zero)
z["q"] += 1
print(z["q"], z["r"], list(z.items()))
s: defaultdict[str, int] = defaultdict(seven)
print(s["a"], list(s.items()) == [("a", 7)])
lam: defaultdict[tuple[int, int], str] = defaultdict(lambda: "?")
print(lam[(1, 2)], list(lam.keys()), len(lam))
# a lambda making another mapping: its result type is the values' (the annotation's)
tree: defaultdict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
tree["a"]["x"] += 1
tree["a"]["y"] += 2
tree["b"]["x"] += 3
print(len(tree), tree["a"], tree["b"]["x"], tree["c"]["z"], sorted(tree), tree["c"])
deep: defaultdict[int, defaultdict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
deep[1]["é"].append(1)
deep[1]["é"].append(2)
print(deep[1], deep[2]["q"], len(deep))
tallies: defaultdict[str, Counter[str]] = defaultdict(lambda: Counter())
tallies["w"].update("hello")
print(tallies["w"], tallies["v"])
ods: defaultdict[int, OrderedDict[str, int]] = defaultdict(lambda: OrderedDict())
ods[1]["k"] = 5
ods[1]["j"] = 6
print(ods[1], list(ods))


def fresh():
    return defaultdict(int, {"start": 1})


made: defaultdict[str, int] = fresh()
made["more"] += 1
print(made)
k = 0


def counter() -> int:
    global k
    k += 1
    return k


cnt: defaultdict[str, int] = defaultdict(counter)
print(cnt["a"], cnt["b"], cnt["a"], list(cnt.values()))
none: defaultdict[str, int] = defaultdict()
print(none, none.default_factory is None)
try:
    print(none["missing"])
except KeyError as ex:
    print("KeyError", ex, repr(ex))
none2: defaultdict[str, int] = defaultdict(None, {"a": 1})
print(none2, none2["a"])
explicit = defaultdict[str, int](int)
explicit["e"] += 2
print(explicit)

# what does not call the factory
g: defaultdict[str, list[int]] = defaultdict(list)
print(g.get("x"), "x" in g, g.get("x", [0]), len(g), g)
print(g.setdefault("y", [5]), g.setdefault("y", [6]), g)
print(g.pop("y"), g.pop("nope", None), g.pop("nope", [0]), g)
try:
    g.pop("nope")
except KeyError as ex:
    print("KeyError", ex)
g["p"].append(1)
g["q"].append(2)
print(g.popitem(), g)
del g["p"]
print(g)
try:
    del g["p"]
except KeyError as ex:
    print("KeyError", ex)
try:
    g.popitem()
except KeyError as ex:
    print("KeyError", ex)

# __missing__ called directly
m: defaultdict[str, int] = defaultdict(int)
print(m.__missing__("x"), m)

# default_factory is writable
f: defaultdict[str, int] = defaultdict(int)
f["a"]
print(f)
f.default_factory = None
print(f)
try:
    f["b"]
except KeyError as ex:
    print("KeyError", ex)
f.default_factory = int
print(f, f["c"])

# copies and |
base: defaultdict[str, list[int]] = defaultdict(list)
base["a"].append(1)
cp = base.copy()
cp["a"].append(2)
cp["b"].append(3)
print(base, cp, base == cp, base != cp)
print(base | {"z": [9]}, base | cp)
base |= {"y": [8]}
print(base)
base.update({"w": [7]}, extra=[6])
base.update([("v", [5])])
base.update(cp)
print(base)
base.clear()
print(base, len(base), bool(base))

# Callable factories
fac: Callable[[], int] = int
viac: defaultdict[str, int] = defaultdict(fac)
viac["x"] += 1
print(viac["x"], viac.default_factory is not None)


# in functions, methods, fields
class Graph:
    def __init__(self) -> None:
        self.edges: defaultdict[str, list[str]] = defaultdict(list)

    def add(self, a: str, b: str) -> None:
        self.edges[a].append(b)
        self.edges[b].append(a)


def group(words: list[str]) -> defaultdict[int, list[str]]:
    out: defaultdict[int, list[str]] = defaultdict(list)
    for word in words:
        out[len(word)].append(word)
    return out


gr = Graph()
gr.add("a", "b")
gr.add("a", "c")
print(gr.edges, group(["hi", "yo", "hey", "a"]))
for key in gr.edges:
    print(key, gr.edges[key])
print(sorted(gr.edges), [x for x in gr.edges], list(gr.edges))

# mutation by the factory, and evaluation order


# a factory that stores the key itself: the value it stored stays (setdefault)
box: defaultdict[str, list[int]] = defaultdict(list)


def sneaky() -> list[int]:
    box["k"] = [99]
    box["other"] = [1]
    return [0]


box.default_factory = sneaky
print(box["k"], list(box.items()))
log: list[str] = []


def getkey(s: str) -> str:
    log.append("key " + s)
    return s


def val(n: int) -> int:
    log.append(f"val {n}")
    return n


od: OrderedDict[str, int] = OrderedDict()
od[getkey("a")] = val(1)
c: Counter[str] = Counter()
c[getkey("b")] += val(2)
d: defaultdict[str, int] = defaultdict(int)
d[getkey("c")] -= val(3)
print(log, od, c, d)


def factory() -> int:
    log.append("factory")
    return 10


f: defaultdict[str, int] = defaultdict(factory)
log.clear()
f[getkey("x")] += val(1)
f[getkey("x")] += val(1)
print(log, list(f.items()))
