# keys() and items() views compare as sets, as CPython's do: equal views need not share an
# insertion order, < and > test proper subsets, and in looks a key up once, calling __hash__
# and __eq__ as CPython does; a size change during a comparison raises CPython's RuntimeError
class K:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, o: "K") -> bool:
        print("  eq", self.v, o.v)
        if self.v == 7 and armed:
            more.clear()
        return self.v == o.v

    def __hash__(self) -> int:
        print("  hash", self.v)
        return self.v % 3


armed = False


class Box:
    def __init__(self) -> None:
        self.d: dict[str, int] = {"a": 1, "b": 2}


def ordered(n: int) -> dict[int, str]:
    d: dict[int, str] = {}
    for i in range(n):
        d[i] = str(i)
    return d


def backwards(n: int) -> dict[int, str]:
    d: dict[int, str] = {}
    for i in range(n - 1, -1, -1):
        d[i] = str(i)
    return d


a = ordered(4)
b = backwards(4)
c = ordered(2)
e: dict[int, str] = {}
print("==", a.keys() == b.keys(), a.items() == b.items(), a.keys() != b.keys(), a.items() != b.items())
print("<", c.keys() < a.keys(), a.keys() < b.keys(), e.keys() < c.keys(), c.items() < b.items())
print("<=", c.keys() <= b.keys(), a.keys() <= b.keys(), b.items() <= c.items())
print(">", b.keys() > c.keys(), a.keys() > b.keys(), b.items() > c.items(), a.keys() >= b.keys(), c.keys() >= a.keys())
odd: dict[int, str] = {3: "3", 1: "1"}
print("subset", odd.keys() < a.keys(), odd.keys() <= b.keys(), odd.items() < b.items(), a.keys() > odd.keys())
b[2] = "two"
print("values", a.keys() == b.keys(), a.items() == b.items(), a.items() != b.items(), c.items() < b.items())
print("in", 2 in b.keys(), 9 in b.keys(), 9 not in b.keys(), (2, "two") in b.items(), (2, "2") in b.items(), (9, "9") in b.items())
k: int | None = None
print("optional", k in a.keys(), True in a.keys())
k = 3
print("optional", k in a.keys(), k not in a.keys())
t: dict[tuple[int, str], int] = {(1, "x"): 1, (2, "y"): 2}
u: dict[tuple[int, str], int] = {(2, "y"): 2, (1, "x"): 1}
print("tuples", t.keys() == u.keys(), t.items() == u.items(), (1, "x") in t.keys(), ((2, "y"), 2) in t.items())
box = Box()
print("field", "a" in box.d.keys(), box.d.keys() == {"b": 0, "a": 1}.keys(), box.d.items() == {"b": 2, "a": 1}.items())
print("display", {i: i for i in range(3)}.keys() == {2: 0, 1: 0, 0: 0}.keys())

objs: dict[K, int] = {K(1): 1, K(2): 2}
same: dict[K, int] = {K(2): 2, K(1): 1}
more: dict[K, int] = {K(1): 1, K(2): 2, K(7): 7}
print("objects in")
print(K(2) in objs.keys())
print("objects items in")
print((K(2), 2) in objs.items())
print("objects ==")
print(objs.keys() == same.keys())
print("objects items ==")
print(objs.items() == same.items())
print("objects <")
print(objs.keys() < more.keys())
print("size change")
other: dict[K, int] = {K(7): 7, K(1): 1, K(2): 2}
armed = True
try:
    print(more.keys() == other.keys())
except RuntimeError as err:
    print("RuntimeError:", err)

big = ordered(3000)
print("lookups", sum(1 for i in range(6000) if i in big.keys()), sum(1 for i in range(3000) if (i, str(i)) in big.items()))
