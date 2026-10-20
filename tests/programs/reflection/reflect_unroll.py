# Loops over constant sets of attribute names (#486): a tuple or list display of str literals, or
# a variable bound once to one and only iterated, unrolled where the body uses the name as an
# attribute name; continue, break and the else block keep their meaning
from operator import attrgetter


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


class Rec:
    def __init__(self) -> None:
        self.name = "rec"
        self.size = 3
        self.ratio = 0.5


p = Point(1, 2)
for name in ("x", "y"):
    print(name, getattr(p, name))
names: list[str] = ["x", "y", "z"]
for name in names:
    if hasattr(p, name):
        print(name, getattr(p, name))
        setattr(p, name, getattr(p, name) * 10)
    else:
        print(name, "missing")
print(p.x, p.y, name)


def total(q: Point) -> int:
    t = 0
    for n in ["x", "y"]:
        if n == "y":
            continue
        t += getattr(q, n)
    else:
        print("else ran")
    for n in ["x", "y"]:
        if n == "x":
            break
        t += 1000
    else:
        print("not printed")
    keys = ("y", "x")
    for k in keys:
        t += getattr(q, k) * 100
    return t


print(total(Point(3, 4)))
r = Rec()
for f in ("name", "size", "ratio"):
    print(f, repr(getattr(r, f)))
for outer in ("x", "y"):
    for inner in ("x", "y"):
        print(outer, inner, getattr(p, outer) + getattr(p, inner))
pts = [Point(3, 1), Point(1, 2)]
for key in ["x", "y"]:
    print(key, [(q.x, q.y) for q in sorted(pts, key=attrgetter(key))])
print([getattr(p, n) for n in ("y", "x")])
cols = ["x", "y"]
print([getattr(p, c) + 1 for c in cols])
