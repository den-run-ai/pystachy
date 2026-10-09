# Functions without parameter annotations are templates: each call compiles them for its
# argument types, the first return statement decides the return type, isinstance() and
# "is None" on parameters are decided by those types, and a parameter defaulting to None can
# get a value of another type outside branches. Never-called templates are not compiled.
from dataclasses import dataclass


@dataclass
class Pt:
    x: int
    y: int

    def __add__(self, o: "Pt") -> "Pt":
        return Pt(self.x + o.x, self.y + o.y)


def add(a, b):
    return a + b


def twice(x):
    return add(x, x)


def first(xs, default=None):
    if len(xs) == 0:
        return default
    return xs[0]


def clamp(x, lo=0, hi=None):
    if hi is None:
        hi = 100
    if x < lo:
        return lo
    return hi if x > hi else x


def describe(v):
    if isinstance(v, str):
        return "str of length " + str(len(v))
    elif isinstance(v, (int, float)):
        return f"number {v}"
    elif isinstance(v, list):
        return f"list of {len(v)}"
    return "something else"


def fact(n):
    if n <= 1:
        return 1
    return n * fact(n - 1)


def total(xs, *, start=0, scale=1):
    s = start
    for x in xs:
        s += x * scale
    return s


def keyed(a, /, b):
    return [a, b]


def collect_into(x, acc: list[int] = []):
    acc.append(x)
    return len(acc)


def maybe_pt(flag):
    if flag:
        return Pt(1, 2)
    return None


def apply_pairs(pairs):
    out = []
    for k, v in pairs:
        out.append(f"{k}={v}")
    return ", ".join(out)


def unused(x):
    try:
        yield x
    except ValueError:
        pass
    return lambda: {x for x in x}


plus = add
print(add(1, 2), add(1.5, 2), add("a", "b"), add([1], [2, 3]), add(Pt(1, 2), Pt(3, 4)), add(True, True))
print(twice(21), twice("ab"), plus(2, 3), plus("x", "y"))
print(first([7, 8], 0), first(["s"], ""), first(["x"][1:], "empty"), first([Pt(5, 6)]), first([Pt(1, 1)][1:]))
print(clamp(5), clamp(-3), clamp(500), clamp(50, hi=40), clamp(7, 10, 20), clamp(2.5, 0.0, 1.0))
print(describe("hey"), describe(3), describe(2.5), describe(True), describe([1, 2]), describe({"a": 1}), describe(Pt(0, 0)))
print(fact(10), fact(1), fact(20))
print(total([1, 2, 3]), total([1.5, 2.5], start=10.0), total([1, 2], scale=3, start=1))
print(keyed(1, 2), keyed("a", b="b"))
print(collect_into(1), collect_into(2), collect_into(3))
print(maybe_pt(True), maybe_pt(False), maybe_pt(True) == Pt(1, 2))
print(apply_pairs([("a", 1), ("b", 2)]), apply_pairs([(1, 2.5)]))
