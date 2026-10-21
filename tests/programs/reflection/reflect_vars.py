# vars(o) and o.__dict__ where they are consumed at once (#486): printed (the runtime walks the
# field table of the object's exact class), iterated (unrolled, each attribute read live),
# formatted with % or str.format_map(), or copied
class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


class Rec:
    kind = "record"

    def __init__(self, name: str, value: int, ratio: float) -> None:
        self.name = name
        self.value = value
        self.ratio = ratio
        self.ok = True
        self.items: list[int] = [1, 2]
        self.where: Point | None = None
        if value > 5:
            self.extra = "big"


class Child(Point):
    def __init__(self) -> None:
        self.first = "c"
        super().__init__(3, 4)
        self.last = [1.5]


class Flat:
    def __init__(self, name: str, value: int, ratio: float) -> None:
        self.name = name
        self.value = value
        self.ratio = ratio


class Node:
    def __init__(self) -> None:
        self.me: "Node | None" = None

    def __repr__(self) -> str:
        return f"Node({vars(self)})"


class Blob:
    def __init__(self) -> None:
        self.tag = "t"
        self.data: bytes = b"\x01z"


p = Point(1, 2)
print(vars(p))
print(Rec("a", 1, 0.5).__dict__)
print(vars(Rec("b", 9, 1.0)))
print(str(vars(p)), repr(p.__dict__), f"<{vars(p)}>")
print(vars(Child()))
xs: list[Point] = [p, Child()]
for x in xs:
    print(vars(x))
n = Node()
n.me = n
print(n)
for k, v in p.__dict__.items():
    print(k, v)
for k in vars(p):
    print(k, getattr(p, k))
for v in vars(p).values():
    print(v)
r = Flat("c", 2, 0.25)
for kv in vars(r).items():
    print(kv)
for k, w in r.__dict__.items():
    if k == "value":
        r.ratio = 9.75
    print(k, w)
fmt = "%(name)s %(value)d"
print(fmt % r.__dict__)
print("%(value)5d|%(name)r|%%" % vars(r))
print("{name}={value:>4} {name!r} {{}}".format_map(vars(r)))
d = dict(vars(p))
d["x"] = 100
print(d, p.x, vars(p).copy())
blob = Blob()
for k in vars(blob):
    print(k, getattr(blob, k))
print(vars(blob))
