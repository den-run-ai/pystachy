# dict[None, V] and dict[K | None, V]: None is a key like any other
def show(d: dict[str | None, int]) -> None:
    print(d, len(d), None in d, list(d.keys()), list(d.values()), list(d.items()))


def strs() -> None:
    d: dict[str | None, int] = {None: 1, "k": 2}
    show(d)
    print(d[None], d["k"], d.get(None), d.get("z"), d.get(None, 9), d.get("z", 9))
    d[None] = 5
    d[None] += 1
    d["k"] -= 1
    show(d)
    k: str | None = None
    print(d[k], k in d, d.get(k))
    k = "k"
    print(d[k], k in d, d.get(k))
    k = "missing"
    print(k in d, d.get(k), d.get(k, -1))
    print(d.pop(None), None in d, d.pop(None, 77), d.setdefault(None, 8), d.setdefault(None, 9))
    try:
        del d[None]
        del d[None]
    except KeyError as e:
        print("KeyError", e)
    try:
        print(d[None])
    except KeyError as e:
        print("KeyError", e)
    try:
        d.pop(None)
    except KeyError as e:
        print("KeyError", e)
    d.update({None: 3, "u": 4})
    show(d)
    e = dict(d)
    c = d.copy()
    d.clear()
    show(e)
    show(c)
    print(e == c, e != c, d == e, e | {None: 0})
    e |= {None: 10, "w": 11}
    show(e)
    for key in e:
        print("key", key, key is None)
    for key, value in e.items():
        print("item", key, value)
    print({key: value * 2 for key, value in e.items()})
    print(sorted([key for key in e if key is not None]), [value for key, value in e.items() if key is None])
    print(e.popitem(), e.popitem(), len(e))
    messages: dict[str | None, list[str]] = {}
    messages.setdefault(None, []).append("a")
    messages.setdefault("f.py", []).append("b")
    messages.setdefault(None, []).append("c")
    print(messages, messages[None], len(messages))
    groups: dict[str | None, list[str]] = {None: ["x"]} if len(messages) > 0 else {}
    print(groups)
    f = dict.fromkeys(["a", None, "a"], 0)
    print(f, len(f))
    many: dict[str | None, int] = {}
    for i in range(100):
        many[str(i)] = i
    many[None] = -1
    for i in range(0, 100, 3):
        del many[str(i)]
    print(len(many), many[None], many["1"], "0" in many, None in many)


def nones() -> None:
    d: dict[None, int] = {None: 1}
    print(d, d[None], None in d, len(d), d.get(None), list(d))
    d[None] = 2
    d[None] += 5
    print(d, d.pop(None), d, None in d, d.get(None), d.get(None, 4))
    d.setdefault(None, 6)
    for k, v in d.items():
        print(k, v)
    e = {None: "x"}
    print(e, e[None])


def ints() -> None:
    d: dict[int | None, str] = {1: "a", None: "n"}
    d[70000] = "big"
    d[1] += "!"
    print(d, len(d), d[1], d[None], d[70000], 1 in d, 2 in d, None in d)
    k: int | None = 70000
    print(d[k], k in d, d.get(k))
    k = None
    print(d[k], k in d, d.get(k))
    k = 5
    print(k in d, d.get(k))
    del d[1]
    print(d.pop(None), d, d.get(None), d.get(1), d.get(70000))
    try:
        print(d[None])
    except KeyError as e:
        print("KeyError", e)
    try:
        print(d[4])
    except KeyError as e:
        print("KeyError", e)
    many: dict[int | None, int] = {}
    for i in range(300):
        many[i * 3] = i
    many[None] = -1
    print(len(many), many[None], many[897], 898 in many, sum(many.values()))
    for i in range(0, 300, 2):
        many.pop(i * 3)
    print(len(many), many[None], 0 in many, 3 in many, [key for key in many if key is None or key < 10])


def tuples() -> None:
    d: dict[tuple[int, str] | None, int] = {(1, "a"): 1, None: 0}
    d[(2, "b")] = 2
    print(d, d[None], d[(1, "a")], (2, "b") in d, (2, "c") in d, None in d)
    k: tuple[int, str] | None = None
    print(d[k], d.get(k))
    k = (2, "b")
    print(d[k], d.get(k))
    del d[None]
    print(d, None in d, d.get(None))


strs()
nones()
ints()
tuples()
