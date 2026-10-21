# pystachy: dynamic-any
# A list or dict of Any values or Any containers is a list[Any] or dict[Any, Any] (#777), whose
# items are boxes, however the compiler builds it: displays, comprehensions, a first store into an
# empty one, list(), sorted(), dict(), dict.fromkeys(), zip(), map() and the rest. Each result is
# printed, which reads every item through its box, as typed and Any code both do.
import itertools
from typing import Any

x: Any = 7
d: dict[str, Any] = {"a": x}
l: list[Any] = [x, "s"]
e: dict[str, Any] = {"b": [x]}
recs: list[dict[str, Any]] = [d, e]


class Holder:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []
        self.index: dict[str, list[Any]] = {}

    def add(self, rec: dict[str, Any]) -> None:
        self.items.append(rec)
        self.index.setdefault("k", []).append(rec)


def made() -> list[dict[str, Any]]:
    return [{"m": x}]


def inferred():
    return [{"i": x}]


def gen():
    yield d
    yield {"g": x}


def acc(r: dict[str, Any], into: list[dict[str, Any]] = []) -> list[dict[str, Any]]:
    into.append(r)
    return into


def displays() -> None:
    print("displays", [d, d], [{"a": x}], [[x]], [[d]], [l, l])
    print("dicts", {"k": d}, {"k": [x]}, {"k": x}, {1: x}, {"n": {"m": l}})
    print("unpacked", [d] * 2, [d] + [d], [*l, *l], [d, *l], {**d, **e}, {"z": 1, **d})


def comprehensions() -> None:
    print("lists", [d for _ in range(2)], [{"a": i} for i in [x, x]], [[v] for v in l])
    print("dicts", {str(i): d for i in range(2)}, {k: x for k in ["a", "b"]}, {k: [k] for k in l})
    print("nested", [[r for r in recs] for _ in range(2)], {k: [v] for k, v in d.items()})
    rows = [{"n": i, "tags": [i, str(i)]} for i in [x, x]]
    rows[0]["tags"].append("more")
    print("rows", rows, [r["n"] for r in rows])


def first_stores() -> None:
    xs = []
    xs.append(d)
    ys = []
    ys.append({"a": x})
    ys.insert(0, d)
    ys.extend([d])
    zs = {}
    zs["a"] = d
    zs.setdefault("b", d)
    ws = [None]
    ws[0] = d
    print("first stores", xs, ys, zs, ws)
    table: dict[str, list[dict[str, Any]]] = {}
    for r in recs:
        table.setdefault("all", []).append(r)
    table["all"][0]["seen"] = True
    print("setdefault", table, d)


def builtins() -> None:
    t = (d, d)
    vt = (l, l)
    print("list", list([d, d]), list(t), list(vt), sorted([x, x]), list(v for v in [d]))
    print("dict", dict(zip(["a"], [d])), dict([("a", d)]), dict.fromkeys(["a", "b"], d), dict(d), d.copy())
    print("iterators", list(map(lambda v: v, [d])), list(filter(None, [d, d])), list(itertools.chain(recs, recs)))
    print("views", list(d.values()), list(d.items()), list(d.keys()))
    print("tuples", list(enumerate([d])), list(zip([d], [l])))
    print("sorted", sorted(recs, key=lambda r: len(r)), list(reversed(recs)), max([d, d], key=len))
    print("slices", recs[0:1], recs[::-1], recs[:], recs.copy(), recs + recs)
    first, *rest = recs
    print("unpacking", first, rest, sum([len(r) for r in recs]), [r for r in recs if "a" in r])


def objects() -> None:
    h = Holder()
    h.add(d)
    h.add({"z": x})
    print("fields", h.items, h.index)
    print("returns", made(), inferred(), list(gen()))
    acc(d)
    print("default", acc(e))
    grid: list[list[Any]] = [[x] * 2 for _ in range(2)]
    grid[0][0] = "changed"
    nested: dict[str, dict[str, Any]] = {"o": {"p": x}}
    nested["o"]["q"] = [x]
    print("annotated", grid, nested)


displays()
comprehensions()
first_stores()
builtins()
objects()
