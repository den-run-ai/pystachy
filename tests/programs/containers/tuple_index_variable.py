# A fixed tuple indexed by a variable gives the item there, of its items' type or of the
# union of their types, and CPython's IndexError past either end; a **kwargs record indexed,
# or searched with get(), by a variable name likewise gives the value of that name (or the
# default), and KeyError for a name it lacks
t = (1, 2)
i = 0
print(t[i], t[i + 1], t[-1 - i])
mixed = (1, "two", 3.5, None, [4], True)
for j in range(-len(mixed), len(mixed)):
    print(j, mixed[j])
for j in [6, -7, 2**40]:
    try:
        print(mixed[j])
    except IndexError as e:
        print("IndexError:", e)
flag = True
print(t[flag], ("a", "b")[not flag])
empty = ()
try:
    print(empty[i])
except IndexError as e:
    print("IndexError:", e)


def at(row, k: int):
    return row[k]


print(at(("é", 2), 0), at(("é", 2), 1), at((1.5, 2.5), 1) + 1.0)
words = ("x", "yy", "zzz")
print([len(words[k]) for k in range(len(words))], max(range(3), key=lambda k: words[k]))


def pick(name: str, **kw):
    return kw[name]


def pick_or(name: str, **kw):
    return kw.get(name, -1)


print(pick("a", a=1, b="x"), pick("b", a=1, b="x"), pick_or("b", a=1.5, b="y"), pick_or("c", a=1.5, b="y"), pick_or("z"))
for name in ["c", "a"]:
    try:
        print(pick(name, a=1, b="x"))
    except KeyError as e:
        print("KeyError:", e)
try:
    print(pick("a"))
except KeyError as e:
    print("KeyError:", e)
