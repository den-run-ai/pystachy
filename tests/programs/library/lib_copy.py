import copy
from dataclasses import dataclass
from typing import NamedTuple


class Point:
    def __init__(self, x: int, y: int, tags: list[str]) -> None:
        self.x = x
        self.y = y
        self.tags = tags

    def __repr__(self) -> str:
        return f"Point({self.x}, {self.y}, {self.tags})"


p = Point(1, 2, ["a"])
q = copy.copy(p)
q.x = 10
q.tags.append("b")
print(p, q, q.tags is p.tags)
d = copy.deepcopy(p)
d.tags.append("c")
print(p, d, d.tags is p.tags)

# containers: shallow copies share their items, deep copies copy them once each
xs = [[1, 2], [3]]
ys = copy.copy(xs)
zs = copy.deepcopy(xs)
xs[0].append(9)
print(xs, ys, zs, ys[0] is xs[0], zs[0] is xs[0])
shared = [1]
dp = copy.deepcopy([shared, shared])
print(dp[0] is dp[1], dp[0] is shared)
m = {"a": [1], "b": [2]}
print(copy.deepcopy(m), copy.copy(m) is m, copy.copy(m) == m)
s = {1, 2, 3}
print(sorted(copy.deepcopy(s)), copy.copy(s) is s, copy.copy(s) == s)
fz = frozenset([1, 2])
print(sorted(copy.deepcopy(fz)), copy.copy(fz) is fz, copy.deepcopy(fz) is fz)
nested = {"k": [{"a": (1, [2])}]}
nc = copy.deepcopy(nested)
nested["k"][0]["a"][1].append(3)
print(nested, nc)

# tuples: a tuple of values that are their own copies is its own copy; one that holds a mutable
# value is copied, and once per deep copy
t = (1, "s", 2.5)
print(copy.deepcopy(t) is t, copy.copy(t) is t)
tl = ([1], [2])
tc = copy.deepcopy(tl)
print(tc, tc is tl, tc[0] is tl[0], copy.copy(tl) is tl)
tt = copy.deepcopy([tl, tl])
print(tt[0] is tt[1], tt[0] is tl)
vt: tuple[str, ...] = ("x", "y")
print(copy.deepcopy(vt) is vt, copy.deepcopy(()) == ())
print(copy.copy(5), copy.deepcopy("s"), copy.copy(None), copy.deepcopy(2.5), copy.deepcopy(b"b"))
print(copy.deepcopy(2**62), copy.copy(True), copy.deepcopy(range(3)), copy.copy(range(2)))


# a tree whose nodes refer to each other: the copy has the same shape, cycles included
class Node:
    def __init__(self, name: str) -> None:
        self.name = name
        self.children: list["Node"] = []
        self.parent: Node | None = None

    def add(self, c: "Node") -> "Node":
        c.parent = self
        self.children.append(c)
        return c


root = Node("root")
a = root.add(Node("a"))
root.add(Node("b"))
a.add(Node("a1"))
r2 = copy.deepcopy(root)
print(r2.name, [c.name for c in r2.children], r2.children[0].parent is r2, r2 is not root)
print(r2.children[0].children[0].parent is r2.children[0], r2.children[0] is not a)
s2 = copy.copy(root)
print(s2.children is root.children, s2.parent is None)


class Base:
    def __init__(self, v: int) -> None:
        self.v = v

    def kind(self) -> str:
        return "base"


class Sub(Base):
    def __init__(self, v: int, extra: list[int]) -> None:
        super().__init__(v)
        self.extra = extra

    def kind(self) -> str:
        return "sub"


class Holder:
    def __init__(self, item: Base) -> None:
        self.item = item


def check_holder() -> None:
    # (a field of the base class's type copies the object of the subclass it holds)
    h = Holder(Sub(3, [1, 2]))
    h2 = copy.deepcopy(h)
    it = h2.item
    print(it.kind(), it.v, isinstance(it, Sub), h2.item is not h.item)
    hi = h.item
    if isinstance(it, Sub) and isinstance(hi, Sub):
        print(it.extra, it.extra is not hi.extra, it.extra == hi.extra)


check_holder()


class Custom:
    def __init__(self, data: list[int]) -> None:
        self.data = data
        self.copies = 0

    def __copy__(self) -> "Custom":
        c = Custom(self.data)
        c.copies = self.copies + 1
        return c

    def __deepcopy__(self, memo) -> "Custom":
        c = Custom(copy.deepcopy(self.data, memo))
        c.copies = self.copies + 10
        return c


cu = Custom([5])
print(copy.copy(cu).copies, copy.deepcopy(cu).copies, copy.deepcopy(cu).data is not cu.data)
pc = copy.deepcopy([cu, cu])
print(pc[0] is pc[1], pc[0].copies)


class Itself:
    calls = 0

    def __deepcopy__(self, memo) -> "Itself":
        Itself.calls += 1
        return self


it2 = Itself()
ic = copy.deepcopy([it2, it2])
print(ic[0] is it2, ic[1] is it2, Itself.calls)


@dataclass(frozen=True)
class Frozen:
    name: str
    items: list[int]


f = Frozen("f", [1])
f2 = copy.deepcopy(f)
f3 = copy.copy(f)
print(f2, f2 == f, f2 is not f, f2.items is not f.items, f3.items is f.items)


class Pt(NamedTuple):
    x: int
    y: int


pt = Pt(1, 2)
print(copy.copy(pt), copy.deepcopy(pt), copy.copy(pt) == pt, copy.deepcopy(pt) == pt)


class Lazy:
    def __init__(self, ready: bool) -> None:
        if ready:
            self.value = [1]

    def get(self) -> list[int]:
        return self.value


lz2 = copy.deepcopy(Lazy(False))
try:
    lz2.get()
except AttributeError as e:
    print("AttributeError", e)
lr = copy.deepcopy(Lazy(True))
print(lr.get())
same = [1, 2]
hc = copy.deepcopy({"x": same, "y": same})
print(hc["x"] is hc["y"], hc["x"] is same)
print(copy.Error.__name__, copy.error is copy.Error, issubclass(copy.Error, Exception))
