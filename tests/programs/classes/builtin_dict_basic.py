# class C(dict) and class C(dict[K, V]): an object is a dict to every operation the class does not
# define (items, views, methods, |, |=, dict(), repr, ==), made as dict() makes one, with the
# class's attributes after the dict's header; a bare base takes its types from the first store.

class Registry(dict[str, int]):
    def total(self) -> int:
        return sum(self.values())

    def names(self) -> list[str]:
        return sorted(self)


r = Registry()
r["a"] = 1
r["b"] = 2
r.update({"c": 3})
r.setdefault("d", 4)
print(r, len(r), r.total(), r.names(), "a" in r, "z" in r, r.get("a"), r.get("z", -1))
print(r["b"], list(r.keys()), list(r.values()), list(r.items()), bool(r), bool(Registry()))
del r["a"]
print(r.pop("b"), r, r == {"c": 3, "d": 4}, r != {}, repr(r), str(r), f"{r}")
print(isinstance(r, dict), isinstance(r, Registry), type(r).__name__, dict(r), type(dict(r)).__name__)
for k in r:
    print(k, r[k], end="; ")
print()
for k, v in r.items():
    print(k, v, end="; ")
print()
try:
    print(r["missing"])
except KeyError as e:
    print("KeyError", e)
r2 = Registry({"x": 1})
print(r2, r2.copy(), type(r2.copy()).__name__, r | {"y": 2}, type(r | {"y": 2}).__name__)
r2 |= {"z": 9}
print(r2, type(r2).__name__, len(r2), sorted(r2.items()))


class Bare(dict):
    def first(self) -> str:
        return sorted(self)[0]


class Made(dict[str, int]):
    pass


class Init(dict[str, int]):
    def __init__(self, base: dict[str, int], tag: str) -> None:
        super().__init__(base)
        self.tag = tag


class Default(dict[str, list[int]]):
    def __missing__(self, key: str) -> list[int]:
        v: list[int] = []
        self[key] = v
        return v


b = Bare()
b["k"] = 1.5
b["a"] = 2.5
print(b, b.first(), len(b))
m = Made({"x": 1, "y": 2})
m2 = Made([("p", 3)])
m3 = Made(q=4, r=5)
m4 = Made({"s": 6}, t=7)
print(m, m2, m3, m4, type(m4).__name__)
i = Init({"a": 1}, "t")
print(i, i.tag, len(i), i == {"a": 1})
d = Default()
d["x"].append(1)
d["x"].append(2)
d["y"].append(3)
print(d, d.get("z"), "z" in d, d.setdefault("w", [9]), d.pop("w"), len(d))
try:
    print(d.pop("nope"))
except KeyError as e:
    print("KeyError", e)
print(d == {"x": [1, 2], "y": [3]}, d != {}, {"x": [1, 2], "y": [3]} == d)
x: Made | None = None
try:
    print(x["a"])
except TypeError as e:
    print("TypeError", e)
try:
    print(len(x))
except TypeError as e:
    print("TypeError", e)
try:
    x["a"] = 1
except TypeError as e:
    print("TypeError", e)
print(x == {}, bool(x), repr(x))
try:
    print({m: 1})
except TypeError as e:
    print("TypeError", e)
print(sorted([Made({"b": 1}), Made()], key=len))


class Opts(dict[str, int]):
    def scaled(self, k: int) -> "Opts":
        out = Opts()
        for key, v in self.items():
            out[key] = v * k
        return out

    def get2(self, key: str) -> int:
        return dict.get(self, key, -1)


def total(d) -> int:
    return sum(d.values())


o = Opts(a=1, b=2)
print({**o, "c": 3}, sorted(o.items()), sorted(o.keys()), list(o.values()))
print(o.scaled(10), type(o.scaled(10)).__name__, o.get2("a"), o.get2("z"), total(o), total(o.scaled(3)))
print(len(o), o.copy(), dict(o), {k: v for k, v in o.items() if v > 1}, "a" in o.keys())
print(isinstance(o, dict), o.popitem(), o, o.setdefault("q", 7), o, list(reversed(o)))
o.clear()
print(o, bool(o), len(o))
