# dictfuse (docs/typed-ir.md 7.1) over what the typed IR adds: a dict wrapped by an object whose
# __contains__ deletes the key, an object's __eq__ that changes the dict, an optional dict, boxed
# values, a NamedTuple's dict field, tuple keys (also with None items) and a class variable's dict.
# Run with PYSTACHY_OPT=-dictfuse too.
from typing import NamedTuple, Optional


class Bag:
    def __init__(self, d: dict[str, int]) -> None:
        self.d = d

    def __contains__(self, k: str) -> bool:
        # deletes the key from the dict it wraps, which is also the caller's dict
        if k in self.d:
            del self.d[k]
            return True
        return False

    def __getitem__(self, k: str) -> int:
        return self.d.get(k, -1)

    def __setitem__(self, k: str, v: int) -> None:
        self.d[k] = v


class Eqx:
    def __init__(self, d: dict[str, int], n: int) -> None:
        self.d = d
        self.n = n

    def __eq__(self, other: "Eqx") -> bool:
        self.d.pop("a", 0)
        return self.n == other.n


class Pt(NamedTuple):
    d: dict[str, int]
    xs: list[int]


class Cv:
    shared: dict[str, int] = {"x": 1}


def through_contains(d: dict[str, int]) -> str:
    b = Bag(d)
    if "a" in d:
        if "a" in b:  # __contains__ deletes "a" from d
            try_get = d.get("a", -100)
            d["a"] = 5  # inserts it again
            return f"get after delete: {try_get} {d}"
    return "no"


def through_eq(d: dict[str, int]) -> str:
    e = Eqx(d, 1)
    es = [Eqx(d, 2), Eqx(d, 1)]
    if "a" in d:
        if e in es:  # __eq__ pops "a"
            d["a"] = 7
            return f"{d}"
    return ""


def obj_protocol(d: dict[str, int]) -> int:
    b = Bag(d)
    if "k" in b:
        b["k"] = b["k"] + 1
    b["z"] = 5
    if "z" in d:
        d["z"] += 1
    return d["z"]


def opt_dict(d: Optional[dict[str, int]], k: str) -> int:
    if d is not None and k in d:
        d[k] += 1
        return d[k]
    return -1


def boxed(d: dict[str, Optional[int]], k: str) -> str:
    if k in d:
        v = d[k]
        if v is not None:
            d[k] = v + 1
        else:
            d[k] = 0
        return f"{d[k]}"
    return "none"


def nt_fields(p: Pt, k: str) -> int:
    if k in p.d:
        p.d[k] += 10
        p.xs.append(p.d[k])
    total = 0
    for x in p.xs:
        total += x
        if x > 100:
            p.xs.clear()
    return total + p.d.get(k, 0)


def tuple_keys(d: dict[tuple[int, str], int], a: int, b: str) -> int:
    if (a, b) in d:
        d[a, b] += 1
    t = (a, b)
    if t in d:
        d[t] = d[t] * 2
    if t not in d:
        d[t] = 0
    else:
        d[t] += 3
    return d[t]


def none_items(d: dict[tuple[int, Optional[str]], int]) -> int:
    t = (1, None)
    if t in d:
        d[t] += 5
    u: tuple[int, Optional[str]] = (2, "x")
    if u in d:
        d[u] = d[u] + 1
    return d[t] * 100 + d.get(u, -1)


def opt_key(d: dict[str, int], k: Optional[str]) -> int:
    if k in d:
        return d[k]
    return -3


def class_var(k: str) -> int:
    if k in Cv.shared:
        Cv.shared[k] += 1
    return Cv.shared[k]


def mutate_in_eq_loop(xs: list[Eqx], d: dict[str, int]) -> int:
    n = 0
    for x in xs:
        if x == xs[0]:
            n += 1
    return n + len(d)


print(through_contains({"a": 1}))
print(through_eq({"a": 1}))
print(obj_protocol({"k": 1}))
print(opt_dict({"q": 1}, "q"), opt_dict(None, "q"), opt_dict({}, "q"))
bd: dict[str, Optional[int]] = {"a": None, "b": 4}
print(boxed(bd, "a"), boxed(bd, "b"), boxed(bd, "c"), bd)
p = Pt({"k": 1}, [1, 2])
print(nt_fields(p, "k"), p)
p2 = Pt({"k": 200}, [150, 2])
print(nt_fields(p2, "k"), p2)
td: dict[tuple[int, str], int] = {(1, "a"): 1}
print(tuple_keys(td, 1, "a"), tuple_keys(td, 2, "b"), td)
nd: dict[tuple[int, Optional[str]], int] = {(1, None): 1, (2, "x"): 7}
print(none_items(nd), nd)
print(opt_key({"a": 3}, "a"), opt_key({"a": 3}, None))
print(class_var("x"), class_var("x"))
dd = {"a": 1, "b": 2}
print(mutate_in_eq_loop([Eqx(dd, 1), Eqx(dd, 1)], dd), dd)
