# A dataclass field annotated float that is given an int (#1534): PEP 484 accepts the int and
# CPython stores it unconverted, so the field holds an int | float, as if annotated so. Each
# object's value keeps its own type: in repr(), isinstance(), arithmetic, comparisons and hash().
from dataclasses import asdict, dataclass, replace


@dataclass
class P:
    x: float
    y: float = 0

    def dot(self, o: "P") -> float:
        return self.x * o.x + self.y * o.y

    def first(self) -> float:
        return self.x


@dataclass(frozen=True)
class F:
    x: float
    y: float


@dataclass
class Q(P):
    z: float = 1

    def first(self) -> float:
        return self.z


p = P(0, 0)
q = P(0.0, 0.0)
r = P(3, 4.5)
print(p.x + 1.5, p, q, r, P(2), repr(r), str(q))
print(r.x + 1, r.x * 2, r.x / 2, r.x // 2, r.x % 2, -r.x, r.y + 1, r.y * 2, r.y // 2)
print(p.x == 0, p.x == q.x, q.x == 0, p.x < 1, r.x > r.y, r.x >= 3, r.x != r.y, r.x <= 3.0)
print(isinstance(p.x, int), isinstance(p.x, float), isinstance(q.x, int), isinstance(q.x, float))
print(p == q, p != q, p == r, r == P(3, 4.5), r == P(3.0, 4.5))
print(bool(p.x), bool(r.x), int(r.y), float(r.x), f"{r.x} {r.y:.2f} {r.x!r}", "%s|%s" % (r.x, r.y))
print(max(r.x, r.y), min(r.x, r.y), sorted([r.y, r.x, p.x]), sum([r.x, r.y]))
print(r.dot(r), P(1, 2).dot(P(3, 4)), isinstance(P(1, 2).dot(P(3, 4)), int), r.first(), q.first())

a = F(0, 0)
b = F(0.0, 0.0)
c = F(1, 2.5)
print(a, b, c, a == b, hash(a) == hash(b), hash(a) == hash(c), hash(c) == hash((1, 2.5)))
seen = {a: "zero", c: "c"}
print(seen[b], seen[F(1.0, 2.5)], len({a, b, c}))
print(hash(p.x) == hash(0), hash(q.x) == hash(0), hash(c.y) == hash(2.5), hash(c.x) == hash(c.y))


def describe(o: P) -> str:
    v = o.x
    if isinstance(v, int):
        return f"int {v + 1}"
    return f"float {v + 0.5}"


print(describe(p), describe(q), describe(r))

print(asdict(r), replace(r, x=2), replace(r, y=3), replace(r, x=1.5, y=2), replace(r) == r)

r.x += 1
print(r, isinstance(r.x, int))
r.x += 0.5
print(r, isinstance(r.x, int))
r.y = 7
r.x = r.y
r.y //= 2
print(r, isinstance(r.y, int))
r.y /= 2
print(r, isinstance(r.y, int))

ps: list[P] = [P(1), Q(1, 2), Q(1.5, 2, 3), Q(0.5), P(0.5, 1)]
for o in ps:
    print(o, o.first(), o.dot(o), isinstance(o.first(), int))
print(Q(1, 2, 3) == Q(1.0, 2.0, 3.0), Q(1) == P(1), Q(2).z + 1)
